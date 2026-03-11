import logging
import socket
import argparse
import re
import requests

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
                    required=True,
                    help='path to text file of gene names (one line per gene)')

args = parser.parse_args()

GENE_FILE = args.gene_names

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
        "from" : "Gene Name",
        "to" : "UniProtKB/Swiss-Prot",
        "ids" : ",".join(gene_list)
    }
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


def main():
    with open(GENE_FILE, "r") as f:
        raw_gene_string = f.read()
        gene_list = parse_gene_file(raw_gene_string)
    
    
if __name__ == "__main__":
    main()