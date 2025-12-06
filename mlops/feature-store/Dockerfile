FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Feast
RUN pip install --no-cache-dir \
    feast[redis]==0.40.1 \
    pandas \
    pyarrow

# Copy feature repository
COPY feature_repo/ /app/feature_repo/

# Create data directory for registry and sample data
RUN mkdir -p /app/data

WORKDIR /app/feature_repo

# Default command: run Feast feature server
CMD ["feast", "serve", "--host", "0.0.0.0", "--port", "6566"]
