#!/bin/bash
set -e

cd /app/feature_repo

# Feature data is provided by Dagster via shared volume at /app/features
# If no feature data exists yet, create sample data for schema validation
FEATURE_PATH="${FEATURE_DATA_PATH:-/app/features}"
if [ ! -f "${FEATURE_PATH}/customer_features.parquet" ]; then
    echo "No feature data found at ${FEATURE_PATH}"
    echo "Creating sample feature data for schema validation..."
    # Update paths in sample data script and run
    FEATURE_DATA_PATH="${FEATURE_PATH}" python create_sample_data.py
fi

# Apply feast definitions if registry is empty
if [ ! -s /app/data/registry.db ] || [ ! -f /app/data/registry.db ]; then
    echo "Applying Feast feature definitions..."
    feast apply
fi

# Start the feast server
exec feast serve --host 0.0.0.0 --port 6566
