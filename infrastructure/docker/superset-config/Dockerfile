# Superset with additional database drivers
FROM apache/superset:latest

USER root

# Install PostgreSQL driver for metadata database
# Install Trino driver for lakehouse queries
# First install pip into venv, then install packages
RUN /app/.venv/bin/python -m ensurepip --upgrade && \
    /app/.venv/bin/python -m pip install --no-cache-dir \
    psycopg2-binary \
    trino[sqlalchemy]

USER superset
