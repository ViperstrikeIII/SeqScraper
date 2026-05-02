FROM python:3.12

# Install NCBI-Blast+ 
RUN apt-get update && \
    apt-get install -y ncbi-blast+ curl && \
    rm -rf /var/lib/apt/lists/*

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY id_mapper.py code/id_mapper.py

RUN chmod a+x /code/id_mapper.py

ENV PATH="/code:$PATH"