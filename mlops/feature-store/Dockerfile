FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Feast with S3 and PostgreSQL registry support
RUN pip install --no-cache-dir \
    feast[redis,postgres]==0.40.1 \
    pandas \
    pyarrow \
    s3fs \
    boto3 \
    psycopg2-binary

# Copy feature repository
COPY feature_repo/ /app/feature_repo/

# Create data directory for registry and sample data
RUN mkdir -p /app/data

# Make entrypoint executable
RUN chmod +x /app/feature_repo/entrypoint.sh

WORKDIR /app/feature_repo

# Use entrypoint to initialize data and apply feast on first run
ENTRYPOINT ["/app/feature_repo/entrypoint.sh"]
