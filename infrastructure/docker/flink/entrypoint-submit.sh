#!/bin/bash
# Flink Job Submitter Entrypoint
# Waits for dependencies and submits SQL jobs from /opt/flink/sql directory

set -e

echo "=================================================="
echo "Flink Job Submitter"
echo "=================================================="
echo ""

# Configuration
FLINK_JOBMANAGER="${FLINK_JOBMANAGER:-flink-jobmanager:8081}"
KAFKA_BROKER="${KAFKA_BROKER:-kafka-broker:29092}"
POLARIS_HOST="${POLARIS_HOST:-polaris:8181}"
MAX_WAIT_SECONDS=120
SLEEP_INTERVAL=5

# 1. Wait for Flink JobManager
echo "Waiting for Flink JobManager at ${FLINK_JOBMANAGER}..."
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT_SECONDS ]; do
    if curl -s "http://${FLINK_JOBMANAGER}/overview" > /dev/null 2>&1; then
        echo "✓ Flink JobManager is ready"
        break
    fi
    echo "  Waiting... (${ELAPSED}s/${MAX_WAIT_SECONDS}s)"
    sleep $SLEEP_INTERVAL
    ELAPSED=$((ELAPSED + SLEEP_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT_SECONDS ]; then
    echo "❌ Error: Flink JobManager not ready"
    exit 1
fi

# 2. Wait for Kafka
echo "Waiting for Kafka at ${KAFKA_BROKER}..."
# Simple TCP check using bash
KAFKA_HOST="${KAFKA_BROKER%:*}"
KAFKA_PORT="${KAFKA_BROKER##*:}"

ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT_SECONDS ]; do
    if (echo > /dev/tcp/$KAFKA_HOST/$KAFKA_PORT) >/dev/null 2>&1; then
        echo "✓ Kafka is ready"
        break
    fi
    echo "  Waiting... (${ELAPSED}s/${MAX_WAIT_SECONDS}s)"
    sleep $SLEEP_INTERVAL
    ELAPSED=$((ELAPSED + SLEEP_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT_SECONDS ]; then
    echo "❌ Error: Kafka not ready"
    exit 1
fi

# 3. Wait for Polaris and verify catalog exists
echo "Waiting for Polaris at ${POLARIS_HOST}..."
ELAPSED=0
POLARIS_READY=false
while [ $ELAPSED -lt $MAX_WAIT_SECONDS ]; do
    if curl -s -u root:secret "http://${POLARIS_HOST}/api/catalog/v1/config" > /dev/null 2>&1; then
        echo "✓ Polaris is ready"
        POLARIS_READY=true
        break
    fi
    echo "  Waiting... (${ELAPSED}s/${MAX_WAIT_SECONDS}s)"
    sleep $SLEEP_INTERVAL
    ELAPSED=$((ELAPSED + SLEEP_INTERVAL))
done

if [ "$POLARIS_READY" = false ]; then
    echo "⚠️  Warning: Polaris not ready. Jobs requiring Polaris will fail."
else
    # Check if catalog 'polariscatalog' exists
    echo "Checking if Polaris catalog 'polariscatalog' exists..."
    ELAPSED=0
    CATALOG_EXISTS=false
    while [ $ELAPSED -lt $MAX_WAIT_SECONDS ]; do
        # Get access token
        TOKEN_RESPONSE=$(curl -s -X POST \
            "http://${POLARIS_HOST}/api/catalog/v1/oauth/tokens" \
            -d "grant_type=client_credentials&client_id=root&client_secret=secret&scope=PRINCIPAL_ROLE:ALL" 2>/dev/null)

        if command -v jq >/dev/null 2>&1; then
            ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token // empty' 2>/dev/null)
        else
            ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p' 2>/dev/null)
        fi

        if [ -n "$ACCESS_TOKEN" ] && [ "$ACCESS_TOKEN" != "null" ]; then
            # Check if catalog exists
            CATALOGS_RESPONSE=$(curl -s -X GET \
                "http://${POLARIS_HOST}/api/management/v1/catalogs" \
                -H "Authorization: Bearer ${ACCESS_TOKEN}" 2>/dev/null)

            if echo "$CATALOGS_RESPONSE" | grep -q '"name":"polariscatalog"'; then
                echo "✓ Polaris catalog 'polariscatalog' exists"
                CATALOG_EXISTS=true
                break
            fi
        fi

        echo "  Waiting for catalog... (${ELAPSED}s/${MAX_WAIT_SECONDS}s)"
        sleep $SLEEP_INTERVAL
        ELAPSED=$((ELAPSED + SLEEP_INTERVAL))
    done

    if [ "$CATALOG_EXISTS" = false ]; then
        echo "⚠️  Warning: Polaris catalog 'polariscatalog' not found."
        echo "   Run 'make docker-polaris-init' to initialize the catalog."
        echo "   Jobs requiring Polaris will fail, but continuing with submission..."
    fi
fi

# 4. Check for existing jobs
echo "Checking for running jobs..."
RUNNING_JOBS=$(curl -s "http://${FLINK_JOBMANAGER}/jobs" | grep -o '"status":"RUNNING"' | wc -l || echo "0")
if [ "$RUNNING_JOBS" -gt 0 ]; then
    echo "✓ Jobs are already running ($RUNNING_JOBS jobs). Skipping submission."
    exit 0
fi

# 5. Submit SQL Files
echo "Submitting SQL files from /opt/flink/sql..."

# Combine all SQL files into one for submission (to handle dependencies if needed, or submit one by one)
# Here we submit them in order: 01_catalogs, 02_tables, 03_jobs
# We use a single session so catalogs persist for the tables/jobs

COMBINED_SQL="/tmp/combined_submission.sql"
rm -f "$COMBINED_SQL"
touch "$COMBINED_SQL"

for sql_file in /opt/flink/sql/*.sql; do
    if [ -f "$sql_file" ]; then
        echo "  Adding $sql_file..."
        cat "$sql_file" >> "$COMBINED_SQL"
        echo "" >> "$COMBINED_SQL" # Ensure newline between files
    fi
done

echo "Submitting combined SQL..."
if /opt/flink/bin/sql-client.sh embedded -f "$COMBINED_SQL"; then
    echo "✓ SQL submission successful"
else
    echo "❌ SQL submission failed"
    exit 1
fi

echo "=================================================="
echo "Job Submission Complete"
echo "=================================================="
