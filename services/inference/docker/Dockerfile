FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy contracts package (dependency)
COPY contracts/ /contracts/

# Copy project files
COPY services/inference/pyproject.toml ./
COPY services/inference/src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir /contracts && pip install --no-cache-dir -e .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8002

# Health check using the /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Run the inference service
CMD ["uvicorn", "inference_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
