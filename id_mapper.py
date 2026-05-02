#!/usr/bin/env python3
import logging
import socket
import argparse
import re
import requests
import time
import pandas as pd
import os
import redis
import io

# ---------------------
# Argument Config
# ---------------------
parser = argparse.ArgumentParser(description = "Use Uniprot ID-Mapper API to obtain protein information from a list of gene names.")

parser.add_argument('-l', '--loglevel',
                    type=str,
                    required=False,
                    default='WARNING',
                    choices = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                    help='set log level to DEBUG, INFO, WARNING, ERROR, or CRITICAL')

parser.add_argument("-g", "--gene-names",
                    type=str,
                    required=False,
                    help='path to text file of gene names (one line per gene)')

parser.add_argument("-o", "--output-file",
                    type=str,
                    required=False,
                    default="my_gene_mapping.tsv",
                    help='path to output tsv file')

args = parser.parse_args()

GENE_FILE = args.gene_names
OUTPUT_TSV = args.output_file

format_str = (
    f'[%(asctime)s {socket.gethostname()}] '
    '%(filename)s:%(funcName)s:%(lineno)s - %(levelname)s: %(message)s'
)

logging.basicConfig(level=args.loglevel, format=format_str)

# ---------------------
# Functions
# ---------------------
def parse_gene_file(gene_names: str) -> list[str]:
    """
    Takes a raw string of gene names and converts them to a list

    Args:
        gene_names: String of gene names seperated by commas, spaces, and/or new lines

    Returns:
        gene_list: List of gene names
    """
    logging.info("Converting raw gene names input to list.")
    gene_list = []
    for gene in re.split(r'[,\n\s]', gene_names):
        if gene.strip():
            logging.debug(f"Adding {gene.strip()} to list.")
            gene_list.append(gene.strip())

    logging.info(f"Finished writing {len(gene_list)} genes to gene list.")
    return gene_list

def post_idmapping_job(gene_list: list[str]) -> str:
    """
    Submit job request to Uniprot ID Mapping Service

    Args:
        gene_list: List of gene names

    Returns:
        job_id: API request job id
        None: An error occured and the API call needs to be retried
    """
    uniprot_url = "https://rest.uniprot.org/idmapping/run"
    submission = {
        "from": "Gene_Name",
        "to": "UniProtKB-Swiss-Prot",
        "ids": ",".join(gene_list),
    }
    logging.info(f"Attempting to post job request to {uniprot_url}")

    try:
        response = requests.post(uniprot_url, data=submission, timeout=(3.05,30))
        response.raise_for_status() # Check if API job went through

        job_id = response.json().get('jobId')
        logging.info(f"Successfully submitted job. ID: {job_id}")
        return job_id
    except requests.exceptions.Timeout:
        logging.error("The request timed out. UniProt might be slow or your internet is lagging.")
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error occured: {e}")

    # Make sure rest of script doesn't run
    return None

def get_job_status(job_id: str) -> bool:
    """
    Checks the status of uniprot id mapping job

    Args:
        job_id: ID of uniprot job

    Returns:
        True: Job finished
        False: Job still running
        None: Job failed
    """
    status_url = "https://rest.uniprot.org/idmapping/status"

    try:
        response = requests.get(f"{status_url}/{job_id}", timeout=(3.05, 10), allow_redirects=False)
        response.raise_for_status()
        status_data = response.json()
        job_status = status_data.get("jobStatus")

        if response.status_code == 303:
            logging.info(f"Job {job_id} finished (Detected via 303 Redirect).")
            return True
        
        if job_status == "FINISHED":
            logging.info(f"Job {job_id} finished.")
            return True
        
        if job_status == "FAILED":
            logging.error(f"Job failed! Reason: {status_data.get('errors')}")
            return None
        
        logging.debug("Job still not finished.")
        return False
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error occured: {e}")
        return None
    except requests.exceptions.Timeout as e:
        logging.error(f"Request to status endpoint failed: {e}")
        return None

def fetch_uniprot_data(job_id: str) -> pd.DataFrame:
    """
    Read in data from uniprot data stream using job id. Output results to tsv.

    Args:
        job_id: ID of uniprot job

    Returns:
        df: Pandas dataframe of Uniprot output
    """
    url = f"https://rest.uniprot.org/idmapping/uniprotkb/results/stream/{job_id}"
    
    params = {
        "format": "tsv",
        "fields": "accession,id,protein_name,gene_names,organism_name,length,sequence",
        "compressed": "false"
    }
    
    logging.info(f"Fetching protein data from: {url}")

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        # Convert the raw text string into an in-memory file to avoid disk writes
        in_memory_file = io.StringIO(response.text)
        
        # Pandas reads in-memory file into a dataframe
        df = pd.read_csv(in_memory_file, sep='\t')
        
        logging.info(f"Successfully loaded {len(df)} records into DataFrame.")
        return df

    except Exception as e:
        logging.error(f"Failed to fetch data into DataFrame: {e}")
        return None
    
def run_mapping_pipeline(gene_list: list[str]) -> pd.DataFrame:
    """
    Runs through uniprot fetching methods from start to finish. Handles waiting and status checking.

    Args:
        gene_list: list of gene names

    Returns:
        dataframe: dataframe of uniprot results to send to Dash
    """
    if not gene_list:
        logging.warning("Gene List is empty. No job submission made.")
        return None

    # Setup Redis Connection
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    try:
        cache = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)
    except redis.ConnectionError:
        logging.warning("Redis is not reachable. Falling back to API.")
        cache = None

    # List of dataframes for each gene
    cached_dataframes = []
    missing_genes = []

    # Check each gene individually in Redis
    for gene in gene_list:
        if cache:
            # Look for the individual gene key
            gene_data = cache.get(f"uniprot_gene:{gene}")
            if gene_data:
                logging.info(f"REDIS HIT: Loaded '{gene}' from Redis.")
                # Convert the saved JSON string back into a DataFrame
                df_part = pd.read_json(io.StringIO(gene_data), orient="records")
                cached_dataframes.append(df_part)
                continue
        
        # If it's not in cache, add it to the missing list
        missing_genes.append(gene)

    # If all genes were in the cache, return concatenated dataframe
    if not missing_genes:
        logging.info("All genes found in database")
        return pd.concat(cached_dataframes, ignore_index=True)

    # Otherwise, query UniProt for the missing genes
    logging.info(f"Querying API for {len(missing_genes)} missing gene(s)...")
    job_id = post_idmapping_job(missing_genes)
    
    if not job_id:
        return None

    # Poll for completion
    job_is_ready = False
    for attempt in range(1, 21):
        status = get_job_status(job_id)
        if status is True:
            job_is_ready = True
            break
        elif status is None:
            break
        time.sleep(5 * attempt)

    if job_is_ready:
        new_df = fetch_uniprot_data(job_id)
        
        if new_df is not None and not new_df.empty:
            # Cache the new results for next time
            if cache:
                for gene in missing_genes:
                    # Filter the DataFrame to grab only rows matching this specific gene
                    # case=False ensures case insensitive
                    gene_subset = new_df[new_df['From'].str.contains(gene, case=False, na=False)]
                    
                    if not gene_subset.empty:
                        # Save this subset's JSON string to its own Redis key
                        cache.set(f"uniprot_gene:{gene}", gene_subset.to_json(orient="records"))
            
            # Add the newly fetched data to our pile of cached data
            cached_dataframes.append(new_df)

        # Stitch everything together into one final DataFrame
        if cached_dataframes:
            final_df = pd.concat(cached_dataframes, ignore_index=True)
            return final_df
            
    return None

def main():
    try:
        with open(GENE_FILE, "r") as f:
            raw_gene_string = f.read()
            genes = parse_gene_file(raw_gene_string)
            
            # Run the pipeline (gets a DataFrame back)
            result_df = run_mapping_pipeline(genes)
            
            if result_df is not None:
                print(f"Successfully retrieved {len(result_df)} records.")
                # Save to TSV only when running from the terminal (testing)
                result_df.to_csv(OUTPUT_TSV, sep='\t', index=False)
                print(f"Saved results to {OUTPUT_TSV}")
                
    except FileNotFoundError:
        logging.error(f"Input gene name file {GENE_FILE} cannot be found.")
    

if __name__ == "__main__":
    main()