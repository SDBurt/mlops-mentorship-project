#!/bin/bash
set -e

cd /app/feature_repo

# Feature data is provided by Dagster via MinIO S3 at s3://features/
# Check if feature data exists on S3, if not create sample data
FEATURE_BUCKET="${FEATURE_S3_BUCKET:-features}"
S3_ENDPOINT="${AWS_ENDPOINT_URL:-http://minio:9000}"

echo "Checking for feature data on S3..."
echo "Bucket: ${FEATURE_BUCKET}, Endpoint: ${S3_ENDPOINT}"

# Use Python to check S3 and create sample data if needed
python -c "
import os
import s3fs

fs = s3fs.S3FileSystem(
    key=os.getenv('AWS_ACCESS_KEY_ID'),
    secret=os.getenv('AWS_SECRET_ACCESS_KEY'),
    endpoint_url='${S3_ENDPOINT}',
)

bucket = '${FEATURE_BUCKET}'
customer_path = f'{bucket}/customer_features.parquet'
merchant_path = f'{bucket}/merchant_features.parquet'

# Check if feature files exist
if not fs.exists(customer_path) or not fs.exists(merchant_path):
    print('Feature data not found on S3. Creating sample data...')
    exec(open('create_sample_data.py').read())
else:
    print('Feature data found on S3')
"

# Always apply feast definitions to ensure registry is up to date
# The PostgreSQL registry handles idempotent updates
echo "Applying Feast feature definitions..."
feast apply

# Start the feast server
exec feast serve --host 0.0.0.0 --port 6566
