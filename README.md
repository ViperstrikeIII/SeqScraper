# SeqScraper (WIP)

A Python-based tool for converting gene names into UniprotKB protein entries and then using those entries to scrape through a fasta file for orthologs.

## Docker Container Setup Instructions

This tool is run using a Docker container built from the Dockerfile found in this folder.

### Build the Image

Run this code to build the image from the repo Dockerfile.\
`-t`: This will assign your image a local name.

```bash
docker build -t seq-scraper .
docker images  # Useful to confirm image was built
```

## Usage Instructions

### `id_mapper.py`

**Packages:** ```Requests```\
**Input File:** ```test_gene_names.txt```\
**Output File:** `my_gene_mapping.tsv`
**Description:** Using the `requests` module and an input file of a list of gene names, request to Uniprot ID Mapping api. Return UniprotKB protein entries as a tsv file.

**Help Message:**

```text
usage: id_mapper.py [-h] [-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}] -g
                    GENE_NAMES [-o OUTPUT_FILE]

Use Uniprot ID-Mapper API to obtain protein information from a list of gene
names.

options:
  -h, --help            show this help message and exit
  -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --loglevel {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        set log level to DEBUG, INFO, WARNING, ERROR, or CRITICAL
  -g GENE_NAMES, --gene-names GENE_NAMES
                        path to text file of gene names (one line per gene)
  -o OUTPUT_FILE, --output-file OUTPUT_FILE
                        path to output tsv file
```

**Example Command:**

```bash
docker run --rm \
    -u $(id -u):$(id -g) \
    -v $(pwd):/data \
    seq-scraper \
    id_mapper.py -l INFO -g /data/test_gene_names.txt -o /data/my_gene_mapping.tsv
```
