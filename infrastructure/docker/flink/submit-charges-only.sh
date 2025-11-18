#!/bin/bash
# Wrapper script for submit-charges-only.sql
# Validates required environment variables and substitutes placeholders before submission

set -e

# Default values (for Docker Compose environment)
POLARIS_URI="${POLARIS_URI:-http://polaris:8181/api/catalog}"
POLARIS_OAUTH_URI="${POLARIS_OAUTH_URI:-http://polaris:8181/api/catalog/v1/oauth/tokens}"
KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-kafka-broker:29092}"

# Validation: Check that variables are set (even if using defaults)
if [ -z "$POLARIS_URI" ] || [ -z "$POLARIS_OAUTH_URI" ] || [ -z "$KAFKA_BOOTSTRAP_SERVERS" ]; then
    echo "❌ Error: Required environment variables not set"
    echo ""
    echo "Required variables:"
    echo "  POLARIS_URI: ${POLARIS_URI:-<not set>}"
    echo "  POLARIS_OAUTH_URI: ${POLARIS_OAUTH_URI:-<not set>}"
    echo "  KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS:-<not set>}"
    echo ""
    echo "Set these in your .env file or export before running:"
    echo "  export POLARIS_URI=http://polaris:8181/api/catalog"
    echo "  export POLARIS_OAUTH_URI=http://polaris:8181/api/catalog/v1/oauth/tokens"
    echo "  export KAFKA_BOOTSTRAP_SERVERS=kafka-broker:29092"
    exit 1
fi

# Display configuration
echo "=================================================="
echo "Flink Charges-Only Job Submission"
echo "=================================================="
echo ""
echo "Configuration:"
echo "  POLARIS_URI: $POLARIS_URI"
echo "  POLARIS_OAUTH_URI: $POLARIS_OAUTH_URI"
echo "  KAFKA_BOOTSTRAP_SERVERS: $KAFKA_BOOTSTRAP_SERVERS"
echo ""

# Locate SQL file (handle both in-container and local execution)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="${SCRIPT_DIR}/submit-charges-only.sql"

if [ ! -f "$SQL_FILE" ]; then
    echo "❌ Error: SQL file not found: $SQL_FILE"
    exit 1
fi

# Create temporary SQL file with substituted values
TEMP_SQL_FILE="/tmp/submit-charges-only-$(date +%s).sql"

# Substitute environment variables in SQL file
# Using envsubst if available, otherwise sed as fallback
if command -v envsubst >/dev/null 2>&1; then
    envsubst < "$SQL_FILE" > "$TEMP_SQL_FILE"
else
    # Fallback: sed substitution (handles ${VAR} syntax)
    sed -e "s|\${POLARIS_URI}|${POLARIS_URI}|g" \
        -e "s|\${POLARIS_OAUTH_URI}|${POLARIS_OAUTH_URI}|g" \
        -e "s|\${KAFKA_BOOTSTRAP_SERVERS}|${KAFKA_BOOTSTRAP_SERVERS}|g" \
        "$SQL_FILE" > "$TEMP_SQL_FILE"
fi

# Verify substitution worked (check for remaining placeholders)
if grep -q '\${' "$TEMP_SQL_FILE"; then
    echo "⚠️  Warning: Some placeholders may not have been substituted:"
    grep -n '\${' "$TEMP_SQL_FILE" || true
    echo ""
fi

echo "Submitting SQL job..."
echo ""

# Submit SQL file to Flink SQL client
if sql-client.sh embedded -f "$TEMP_SQL_FILE"; then
    echo ""
    echo "✓ Job submitted successfully!"
    echo ""
    echo "Verify job status:"
    echo "  1. Flink Web UI: http://localhost:8081"
    echo "  2. Query data: make flink-attach"
    echo "     SELECT COUNT(*) FROM polaris_catalog.payments_db.payment_charges;"
else
    echo ""
    echo "❌ Error: Job submission failed"
    echo "Check Flink logs for details"
    exit 1
fi

# Cleanup temporary file
rm -f "$TEMP_SQL_FILE"
