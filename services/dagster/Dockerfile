# Dockerfile for Dagster User Code - orchestration-dagster
# This containerizes the orchestration_dagster package for deployment to Kubernetes

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy contracts package (dependency)
COPY contracts/ /contracts/

# Copy project files
COPY services/dagster/pyproject.toml ./
COPY services/dagster/src/ ./src/
COPY services/dagster/README.md ./

# Install Python dependencies using pip
# Note: Using pip instead of uv for simpler container builds
RUN pip install --no-cache-dir /contracts && pip install --no-cache-dir -e .

# Expose Dagster gRPC server port
EXPOSE 3030

# Run Dagster code server
# The code server provides the definitions to the Dagster webserver/daemon
CMD ["dagster", "code-server", "start", \
     "--host", "0.0.0.0", \
     "--port", "3030", \
     "--module-name", "orchestration_dagster.definitions"]
