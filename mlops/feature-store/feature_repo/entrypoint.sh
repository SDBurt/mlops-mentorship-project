#!/bin/bash
set -e

cd /app/feature_repo

# Create sample data if it doesn't exist
if [ ! -f /app/data/customer_features.parquet ]; then
    echo "Creating sample feature data..."
    python create_sample_data.py
fi

# Apply feast definitions if registry is empty
if [ ! -s /app/data/registry.db ] || [ ! -f /app/data/registry.db ]; then
    echo "Applying Feast feature definitions..."
    feast apply
fi

# Start the feast server
exec feast serve --host 0.0.0.0 --port 6566
