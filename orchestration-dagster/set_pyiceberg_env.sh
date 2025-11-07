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

# IMPORTANT: Replace these credentials with dagster_user credentials from init-polaris.sh
# After running 'make init-polaris', the credentials will be saved to:
#   infrastructure/kubernetes/polaris/.credentials/dagster_user.txt
#
# Run: source infrastructure/kubernetes/polaris/.credentials/dagster_user.txt
# Or manually copy the POLARIS_CLIENT_ID and POLARIS_CLIENT_SECRET values here.
#
# Security Note: Use dagster_user service account (not polaris_admin) for Dagster operations
export PYICEBERG_CATALOG__DEFAULT__CREDENTIAL="${POLARIS_CLIENT_ID:-polaris_admin}:${POLARIS_CLIENT_SECRET:-polaris_admin_secret}"

# S3/MinIO configuration (127.0.0.1 for port-forward development)
# Note: Using 127.0.0.1 instead of localhost to avoid PyArrow DNS resolution issues
# IMPORTANT: These credentials should be set in .env file or environment
# For production, use Kubernetes Secrets instead of hardcoded values
export PYICEBERG_CATALOG__DEFAULT__S3__ENDPOINT="${PYICEBERG_CATALOG__DEFAULT__S3__ENDPOINT:-http://127.0.0.1:9000}"
export PYICEBERG_CATALOG__DEFAULT__S3__ACCESS_KEY_ID="${PYICEBERG_CATALOG__DEFAULT__S3__ACCESS_KEY_ID:-admin}"
export PYICEBERG_CATALOG__DEFAULT__S3__SECRET_ACCESS_KEY="${PYICEBERG_CATALOG__DEFAULT__S3__SECRET_ACCESS_KEY:-CHANGEME_MINIO_PASSWORD}"
export PYICEBERG_CATALOG__DEFAULT__S3__PATH_STYLE_ACCESS="${PYICEBERG_CATALOG__DEFAULT__S3__PATH_STYLE_ACCESS:-true}"
export PYICEBERG_CATALOG__DEFAULT__S3__REGION="${PYICEBERG_CATALOG__DEFAULT__S3__REGION:-us-east-1}"

export PYICEBERG_CATALOG__LAKEHOUSE__S3__ENDPOINT="${PYICEBERG_CATALOG__LAKEHOUSE__S3__ENDPOINT:-http://127.0.0.1:9000}"
export PYICEBERG_CATALOG__LAKEHOUSE__S3__PATH_STYLE_ACCESS="${PYICEBERG_CATALOG__LAKEHOUSE__S3__PATH_STYLE_ACCESS:-true}"

# AWS SDK configuration to prevent metadata service timeouts (WSL2 fix)
# Disable EC2 metadata service which causes timeouts in local/WSL2 environments
export AWS_EC2_METADATA_DISABLED="${AWS_EC2_METADATA_DISABLED:-true}"
# Use static credentials to avoid credential chain lookups
# IMPORTANT: Set these in .env file - do not hardcode production credentials
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-admin}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-CHANGEME_MINIO_PASSWORD}"
export AWS_DEFAULT_REGION="us-east-1"
# Force AWS SDK to use 127.0.0.1 for S3 endpoint (highest precedence)
export AWS_ENDPOINT_URL_S3="http://127.0.0.1:9000"
export AWS_ENDPOINT_URL="http://127.0.0.1:9000"
# Reduce connection timeout for faster failures
export PYICEBERG_CATALOG__DEFAULT__S3__CONNECT_TIMEOUT="5"

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
echo "  Storage: MinIO at http://127.0.0.1:9000"
echo ""

# Check if using proper dagster_user credentials
if [ "${POLARIS_CLIENT_ID:-polaris_admin}" = "polaris_admin" ]; then
    echo "⚠️  WARNING: Using bootstrap credentials (polaris_admin)"
    echo "  For production, you should:"
    echo "  1. Run: make init-polaris"
    echo "  2. Source the credentials: source infrastructure/kubernetes/polaris/.credentials/dagster_user.txt"
    echo "  3. Re-run: source set_pyiceberg_env.sh"
    echo ""
else
    echo "✓ Using dagster_user service account credentials (Client ID: ${POLARIS_CLIENT_ID:0:8}...)"
    echo ""
fi

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
