# Dockerfile for Temporal payment worker
#
# Build:
#   docker build -t temporal-worker .
#
# Run worker:
#   docker run --rm -e TEMPORAL_HOST=temporal:7233 -e KAFKA_BOOTSTRAP_SERVERS=kafka:9092 temporal-worker
#
# Run generator:
#   docker run --rm -e TEMPORAL_HOST=temporal:7233 temporal-worker uv run python -m temporal.payment_generator

FROM python:3.11-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy source code
COPY temporal/ ./temporal/
COPY tests/ ./tests/

# Default command: run the worker
CMD ["uv", "run", "python", "-m", "temporal.worker"]
