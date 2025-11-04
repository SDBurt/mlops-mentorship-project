#!/bin/bash
# PyIceberg environment variables for Apache Polaris REST catalog
# Source this file before running dagster dev: source set_pyiceberg_env.sh

# Auto-load .env file from project root if it exists
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "Loading environment variables from $PROJECT_ROOT/.env"
    set -a  # Export all variables
    source "$PROJECT_ROOT/.env"
    set +a  # Stop exporting
else
    echo "Note: No .env file found at $PROJECT_ROOT/.env"
fi

# Polaris REST catalog configuration (localhost for port-forward development)
export PYICEBERG_CATALOG__DEFAULT__URI="http://localhost:8181/api/catalog"
export PYICEBERG_CATALOG__DEFAULT__WAREHOUSE="lakehouse"
export PYICEBERG_CATALOG__DEFAULT__TYPE="rest"
export PYICEBERG_CATALOG__DEFAULT__CREDENTIAL="polaris_admin:polaris_admin_secret"

# S3/MinIO configuration (localhost for port-forward development)
export PYICEBERG_CATALOG__DEFAULT__S3__ENDPOINT="http://localhost:9000"
export PYICEBERG_CATALOG__DEFAULT__S3__ACCESS_KEY_ID="admin"
export PYICEBERG_CATALOG__DEFAULT__S3__SECRET_ACCESS_KEY="minio123"
export PYICEBERG_CATALOG__DEFAULT__S3__PATH_STYLE_ACCESS="true"
export PYICEBERG_CATALOG__DEFAULT__S3__REGION="us-east-1"

# Reddit API credentials (for PRAW)
# These should be set in .env file at project root
# If not set, use empty defaults (will cause assets to fail with clear error message)
export REDDIT_CLIENT_ID="${REDDIT_CLIENT_ID:-}"
export REDDIT_CLIENT_SECRET="${REDDIT_CLIENT_SECRET:-}"
export REDDIT_USER_AGENT="${REDDIT_USER_AGENT:-lakehouse:v1.0.0 (by /u/your_username)}"

echo ""
echo "PyIceberg environment variables set for Apache Polaris REST catalog"
echo "  Catalog: lakehouse"
echo "  Endpoint: http://localhost:8181/api/catalog"
echo "  Storage: MinIO at http://localhost:9000"
echo ""
echo "Note: These endpoints use localhost (for port-forward development)."
echo "      For in-cluster deployment, the code defaults to cluster DNS:"
echo "      - Polaris: http://polaris:8181/api/catalog"
echo "      - MinIO: http://minio:9000"
echo ""

# Validate Reddit credentials are set
if [ -z "$REDDIT_CLIENT_ID" ] || [ -z "$REDDIT_CLIENT_SECRET" ]; then
    echo "⚠️  WARNING: Reddit API credentials not set!"
    echo "  Reddit assets will fail to materialize."
    echo "  Add credentials to $PROJECT_ROOT/.env:"
    echo "    REDDIT_CLIENT_ID=\"your_client_id\""
    echo "    REDDIT_CLIENT_SECRET=\"your_client_secret\""
    echo "    REDDIT_USER_AGENT=\"your_user_agent\""
    echo ""
else
    echo "✓ Reddit API credentials loaded (Client ID: ${REDDIT_CLIENT_ID:0:8}...)"
    echo ""
fi
