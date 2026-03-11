import logging
import socket
import argparse
import re

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
def parse_gene_file(gene_names: str) -> list:
    """
    Takes a raw string of gene names and converts them to a list

    Args:
        gene_names: String of gene names seperated by commas, spaces, and/or new lines

    Returns:
        gene_list: List of gene names
    """
    gene_list = []
    logging.info("Converting raw gene names input to list.")
    for gene in re.split(r'[,\n\s]', gene_names):
        if gene.strip():
            logging.debug(f"Adding {gene.strip()} to list.")
            gene_list.append(gene.strip())
    logging.info(f"Finished writing {len(gene_list)} genes to gene list.")
    return gene_list
    

def main():
    with open(GENE_FILE, "r") as f:
        raw_gene_string = f.read()
        gene_list = parse_gene_file(raw_gene_string)
    
    
if __name__ == "__main__":
    main()