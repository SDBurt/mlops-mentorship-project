FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl procps && \
    rm -rf /var/lib/apt/lists/*

# Copy contracts package (dependency)
COPY contracts/ /contracts/

# Copy project files
COPY services/temporal/pyproject.toml ./
COPY services/temporal/src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir /contracts && pip install --no-cache-dir -e .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check - verify the process is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f "temporal_worker.main" || exit 1

# Run the Temporal worker
CMD ["python", "-m", "temporal_worker.main"]
