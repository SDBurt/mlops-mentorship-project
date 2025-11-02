# Iceberg + Merge Setup Guide

This document explains the current state of Iceberg configuration and the path to enable merge/ACID operations.

## Current Status

### Working
- ✅ dlt → Garage S3 connection (Parquet files)
- ✅ Reddit REST API source with parent-child relationships
- ✅ Dagster partitioning (5 subreddits)
- ✅ OAuth2 authentication with `@configspec`
- ✅ Response actions for nested Reddit API format
- ✅ Proper S3 configuration for Garage compatibility

### Blocked
- ❌ PyIceberg direct writes to Garage S3
  - Cause: Garage doesn't support checksum algorithms used by PyArrow multipart uploads
  - Error: `invalid checksum algorithm` during Iceberg metadata creation

## Key Configuration Fixes Applied

### 1. S3 Region Configuration
**Problem**: Garage rejected `region_name="garage"` with SigV4 scope errors

**Fix**: Use standard AWS region
```toml
# .dlt/config.toml
[destination.filesystem.credentials]
region_name = "us-east-1"  # Must use standard AWS region, not "garage"
```

### 2. Path-Style Access
**Problem**: Virtual-hosted-style URLs don't work with Garage

**Fix**: Enable path-style endpoints
```toml
[destination.filesystem.credentials.client_kwargs]
use_path_style_endpoint = true
use_ssl = false
```

## Architecture: Parquet → Trino Iceberg

Since PyIceberg can't write directly to Garage, we use a two-tier approach:

```
dlt → Parquet Files (Garage S3)
         ↓
   Trino Iceberg Tables
         ↓
   Merge/ACID Operations
```

### Flow
1. **dlt writes Parquet**: Regular Parquet files to `s3://lakehouse/reddit/<subreddit>/`
2. **Trino creates Iceberg tables**: Point to Parquet location with Iceberg metadata
3. **Trino handles merges**: ACID operations via Iceberg catalog

## Next Steps

### Step 1: Run Reddit Pipeline (Write Parquet)
```bash
# Port-forward Dagster UI
kubectl port-forward -n lakehouse svc/dagster-dagster-webserver 3000:80

# Materialize assets in Dagster UI
# Visit: http://localhost:3000
# Select: reddit_posts_comments
# Click: Materialize with partitions
```

### Step 2: Verify Parquet Files in Garage
```bash
POD=$(kubectl get pods -n lakehouse -l app.kubernetes.io/name=garage -o jsonpath='{.items[0].metadata.name}')

# List Parquet files
kubectl exec -n lakehouse $POD -- mc ls garage/lakehouse/reddit/ --recursive
```

### Step 3: Create Iceberg Tables in Trino

#### Option A: Via Trino SQL
```sql
-- Port-forward Trino
kubectl port-forward -n lakehouse svc/trino 8080:8080

-- Connect to Trino
trino --server http://localhost:8080

-- Create Iceberg catalog (if not exists)
CREATE SCHEMA IF NOT EXISTS iceberg.reddit;

-- Create Iceberg table from Parquet location
CREATE TABLE iceberg.reddit.posts (
    id VARCHAR,
    subreddit VARCHAR,
    title VARCHAR,
    author VARCHAR,
    score BIGINT,
    created_utc BIGINT,
    url VARCHAR,
    -- Add other Reddit post fields
    _posts_id VARCHAR,  -- Parent FK from dlt
    _dlt_load_id VARCHAR,
    _dlt_id VARCHAR
)
WITH (
    format = 'PARQUET',
    location = 's3://lakehouse/reddit/posts/',
    partitioning = ARRAY['subreddit']
);

-- Create comments table
CREATE TABLE iceberg.reddit.comments (
    id VARCHAR,
    subreddit VARCHAR,
    body VARCHAR,
    author VARCHAR,
    score BIGINT,
    created_utc BIGINT,
    _posts_id VARCHAR,  -- FK to posts
    _dlt_load_id VARCHAR,
    _dlt_id VARCHAR
)
WITH (
    format = 'PARQUET',
    location = 's3://lakehouse/reddit/comments/',
    partitioning = ARRAY['subreddit']
);
```

#### Option B: Via Python (pyiceberg)
```python
from pyiceberg.catalog import load_catalog

catalog = load_catalog("default")

# Register existing Parquet files as Iceberg table
catalog.register_table(
    identifier=("reddit", "posts"),
    metadata_location="s3://lakehouse/reddit/posts/"
)
```

### Step 4: Enable Merge in dlt

Once Iceberg tables exist in Trino, update `source.py`:

```python
# Change write_disposition from "append" to "merge"
{
    "name": "posts",
    "write_disposition": "merge",  # Now Trino handles merge
    "primary_key": "id",
    ...
}
```

### Step 5: Verify Merge Behavior

```sql
-- Check record count before
SELECT COUNT(*) FROM iceberg.reddit.posts;

-- Run dlt pipeline again (should merge/dedupe)

-- Check record count after (should be same or fewer)
SELECT COUNT(*) FROM iceberg.reddit.posts;

-- Verify no duplicates by primary key
SELECT id, COUNT(*) as cnt
FROM iceberg.reddit.posts
GROUP BY id
HAVING COUNT(*) > 1;  -- Should return 0 rows
```

## Alternative: Replace Garage with MinIO

If Trino Iceberg approach proves complex, consider replacing Garage with MinIO:

### Why MinIO?
- ✅ Better S3 API compatibility
- ✅ Supports all checksum algorithms
- ✅ PyIceberg works natively
- ✅ Direct merge writes via dlt

### Migration Steps
1. Deploy MinIO to lakehouse namespace
2. Update `.dlt/secrets.toml` endpoint_url
3. Re-enable `table_format="iceberg"` in source.py
4. Run pipeline (should work end-to-end)

## Testing

Test S3 connection:
```bash
uv run python test_s3_connection.py
```

Test Reddit source (without Iceberg):
```bash
# In Dagster UI, materialize one partition
# Check Garage for Parquet files
```

## References

- [dlt Filesystem Destination](https://dlthub.com/docs/dlt-ecosystem/destinations/filesystem)
- [dlt Iceberg Support](https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg)
- [Trino Iceberg Connector](https://trino.io/docs/current/connector/iceberg.html)
- [Garage S3 Compatibility](https://garagehq.deuxfleurs.fr/documentation/reference-manual/s3-compatibility/)
- [PyIceberg](https://py.iceberg.apache.org/)
