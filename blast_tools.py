import subprocess
import pandas as pd
import os

def build_blast_db(fasta_path: str):
    """
    Runs makeblastdb on the uploaded nucleotide FASTA.

    Args:
        fasta_path: Path to target fasta file uploaded by user
    """
    # Check if file exists
    if not os.path.exists(fasta_path):
        raise FileNotFoundError(f"Cannot find database file: {fasta_path}")

    # Creates blast database to search against (target)
    command = [
        "makeblastdb",
        "-in", fasta_path,
        "-dbtype", "nucl",
        "-parse_seqids"
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return True

def run_tblastn(query_path: str, db_path: str, output_path: str = "/app/data/blast_results.tsv"):
    """
    Runs tblastn and returns the results as a Pandas DataFrame.

    Args:
        query_path: location of gene query sequences
        db_path: location of target sequences
        output_path: location to write results of tblastn
    """
    if not os.path.exists(query_path) or not os.path.exists(db_path):
        raise FileNotFoundError("Missing query or database FASTA file.")

    command = [
        "tblastn",
        "-query", query_path,
        "-db", db_path,
        "-outfmt", "6",
        "-out", output_path
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    
    blast_columns = [
        "Query ID", "Subject ID", "% Identity", "Alignment Length", 
        "Mismatches", "Gap Opens", "Q. Start", "Q. End", 
        "S. Start", "S. End", "E-value", "Bit Score"
    ]
    
    try:
        df = pd.read_csv(output_path, sep="\t", names=blast_columns)
        return df
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=blast_columns)

def extract_hit_sequences(db_path: str, selected_hits: list, output_path: str = "/app/data/final_extracted_hits.fasta"):
    """
    Uses blastdbcmd to extract target sequences from the DB based on tblastn hits.
    Prevents duplicate extraction if multiple hits target the same subject sequence.
    """
    extracted_subjects = set() # Used to track what we have already downloaded
    
    with open(output_path, "w") as out_fasta:
        for hit in selected_hits:
            subject_id = hit["Subject ID"]
            
            # Skip if we already pulled this full sequence for a previous hit
            if subject_id in extracted_subjects:
                continue
                
            # Mark this sequence as downloaded
            extracted_subjects.add(subject_id)
            
            command = [
                "blastdbcmd",
                "-db", db_path,
                "-entry", str(subject_id)
            ]
            
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.stdout:
                header_split = result.stdout.strip().split('\n')
                raw_header = header_split[0]
                sequence_lines = header_split[1:]

                # Add extra context to the FASTA header so the biologist knows why it was pulled
                custom_header = f"{raw_header} [Full Sequence Extracted via Query: {hit['Query ID']}]"
                
                out_fasta.write(custom_header + "\n")
                out_fasta.write("\n".join(sequence_lines) + "\n")
                
    return output_path