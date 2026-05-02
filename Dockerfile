FROM python:3.12

# Install NCBI BLAST+ suite (makeblastdb, tblastn, blastdbcmd)
RUN apt-get update && apt-get install -y \
    ncbi-blast+ \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all python scripts into the container
COPY . .

# Expose the Dash port
EXPOSE 8050

# Command to run Dash app
CMD ["python", "app.py"]