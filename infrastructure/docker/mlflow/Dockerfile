FROM ghcr.io/mlflow/mlflow:v2.17.0

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install PostgreSQL driver and S3 support
RUN pip install --no-cache-dir \
    psycopg2-binary \
    boto3
