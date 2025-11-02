# Trino - Distributed SQL Query Engine

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established Trino concepts and this project's architecture, please verify critical details against official Trino documentation and your specific use cases.

## Overview

Trino (formerly PrestoSQL) is a distributed SQL query engine designed for fast analytics over large datasets. It queries data where it lives (S3, HDFS, databases) without moving it - a federated query model.

In this lakehouse platform, Trino is the query engine: it reads [Apache Iceberg](apache-iceberg.md) tables from [MinIO](minio.md) S3, executes [DBT](dbt.md) transformations, and powers analytics across the [Medallion Architecture](medallion-architecture.md).

## Why Trino for This Platform?

**Fast Analytics**: Distributed execution across multiple workers for parallel processing.

**Iceberg Native**: First-class support for [Apache Iceberg](apache-iceberg.md) (ACID, time travel, schema evolution).

**SQL Standard**: ANSI SQL interface - familiar to analysts and data engineers.

**Query Federation**: Join data across multiple sources (Iceberg + Postgres + MongoDB) in single query.

**No Data Movement**: Queries data in place (S3), no ETL to separate warehouse.

## Key Concepts

### 1. Architecture

**Coordinator**: Query planner and scheduler
- Receives SQL queries
- Parses and optimizes execution plan
- Schedules tasks across workers
- Aggregates final results

**Workers**: Query executors
- Execute query fragments in parallel
- Read data from sources (S3, databases)
- Process and filter data locally
- Return results to coordinator

**Connectors**: Plugins for data sources
- Iceberg connector → [MinIO](minio.md) S3
- Hive connector → [Hive Metastore](hive-metastore.md)
- Postgres connector → PostgreSQL databases

**Query flow**:
```
Client → Coordinator (parse SQL, create plan)
    ↓
Coordinator → Workers (distribute tasks)
    ↓
Workers → MinIO S3 (read Parquet files)
    ↓
Workers → Coordinator (partial results)
    ↓
Coordinator → Client (final aggregated result)
```

### 2. Catalogs and Schemas

**Catalog**: Named connection to data source

**In this platform**:
- `iceberg` catalog → Iceberg tables in MinIO S3
- `lakehouse` database within `iceberg` catalog
- `analytics` schema within `lakehouse` database

**Fully qualified table name**:
```sql
SELECT * FROM iceberg.lakehouse.analytics.dim_customer;
--               ↑       ↑         ↑           ↑
--            catalog database  schema     table
```

**Short form** (with session defaults):
```sql
USE iceberg.lakehouse.analytics;
SELECT * FROM dim_customer;
```

### 3. Iceberg Connector Configuration

**Trino values.yaml**:
```yaml
coordinator:
  additionalCatalogs:
    iceberg: |
      connector.name=iceberg
      iceberg.catalog.type=hive_metastore
      hive.metastore.uri=thrift://hive-metastore.database.svc.cluster.local:9083
      hive.s3.endpoint=http://minio:3900
      hive.s3.path-style-access=true
      hive.s3.aws-access-key=<from-minio-key-create>
      hive.s3.aws-secret-key=<from-minio-key-create>
      hive.s3.region=minio
      iceberg.file-format=PARQUET
```

**Key properties**:
- `iceberg.catalog.type`: Metadata store (hive_metastore or rest)
- `hive.s3.endpoint`: [MinIO](minio.md) S3 API endpoint
- `hive.s3.path-style-access`: Required for MinIO (not virtual-hosted style)
- `iceberg.file-format`: Default format for new tables (PARQUET recommended)

### 4. Query Optimization

**Predicate Pushdown**: Filters pushed to storage layer
```sql
-- Only reads files for 2025-01-20 (partition pruning)
SELECT * FROM orders
WHERE order_date = DATE '2025-01-20';
```

**Projection Pushdown**: Only requested columns read
```sql
-- Only reads customer_id and email columns from Parquet
SELECT customer_id, email FROM dim_customer;
```

**File Pruning**: Skips files based on Iceberg metadata
```sql
-- Iceberg manifest tracks min/max values per file
-- Skips files where id < 1000 or id > 2000
SELECT * FROM customers WHERE id BETWEEN 1000 AND 2000;
```

**Cost-Based Optimization**: Query planner chooses optimal join order
```sql
-- Trino analyzes table sizes and chooses broadcast vs shuffle join
SELECT o.*, c.name
FROM orders o
JOIN dim_customer c ON o.customer_key = c.customer_key;
```

## Deployment in Kubernetes

**Helm deployment**:
```bash
helm upgrade --install trino trino/trino \
  -f infrastructure/kubernetes/trino/values.yaml \
  -n lakehouse --create-namespace --wait --timeout 10m
```

**Components**:
- `trino-coordinator`: Single pod (query planner)
- `trino-worker`: Multiple pods (scalable query executors)

**Accessing Trino**:
```bash
# Port-forward UI
kubectl port-forward -n lakehouse svc/trino 8081:8080

# Access UI: http://localhost:8081

# CLI access
TRINO_POD=$(kubectl get pod -n lakehouse -l app.kubernetes.io/component=coordinator -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it -n lakehouse $TRINO_POD -- trino
```

## Common SQL Operations

### Create Iceberg Table

```sql
CREATE TABLE lakehouse.analytics.dim_customer (
    customer_key BIGINT,
    customer_id VARCHAR,
    email VARCHAR,
    first_name VARCHAR,
    last_name VARCHAR,
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,
    is_current BOOLEAN
)
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['month(valid_from)'],
    location = 's3://lakehouse/warehouse/analytics/dim_customer/'
);
```

### Insert Data

```sql
INSERT INTO lakehouse.analytics.dim_customer
SELECT
    ROW_NUMBER() OVER (ORDER BY customer_id) as customer_key,
    customer_id,
    email,
    first_name,
    last_name,
    CURRENT_TIMESTAMP as valid_from,
    NULL as valid_to,
    TRUE as is_current
FROM lakehouse.raw.customers;
```

### Query with Time Travel

```sql
-- Current data
SELECT COUNT(*) FROM dim_customer;

-- Data as of specific snapshot
SELECT COUNT(*) FROM dim_customer FOR VERSION AS OF 100;

-- Data as of timestamp
SELECT COUNT(*) FROM dim_customer FOR TIMESTAMP AS OF TIMESTAMP '2025-01-20 10:00:00';
```

### View Metadata

```sql
-- Table snapshots
SELECT * FROM "lakehouse.analytics.dim_customer$snapshots"
ORDER BY committed_at DESC
LIMIT 10;

-- Data files
SELECT * FROM "lakehouse.analytics.dim_customer$files";

-- Table history
SELECT * FROM "lakehouse.analytics.dim_customer$history";

-- Partitions
SELECT * FROM "lakehouse.analytics.dim_customer$partitions";
```

### Expire Old Snapshots

```sql
CALL iceberg.system.expire_snapshots(
  schema => 'lakehouse.analytics',
  table => 'dim_customer',
  older_than => TIMESTAMP '2025-01-15 00:00:00',
  retain_last => 100
);
```

### Compact Small Files

```sql
CALL iceberg.system.rewrite_data_files(
  schema => 'lakehouse.analytics',
  table => 'dim_customer',
  options => MAP(
    ARRAY['target_file_size_mb'],
    ARRAY['512']
  )
);
```

## DBT Integration

**DBT profiles.yml**:
```yaml
lakehouse:
  outputs:
    dev:
      type: trino
      host: localhost  # Via port-forward
      port: 8080
      database: lakehouse
      schema: analytics
      user: trino

    prod:
      type: trino
      host: trino  # From within cluster
      port: 8080
      database: lakehouse
      schema: analytics
      user: trino
```

**DBT model executes on Trino**:
```sql
-- models/silver/dim_customer.sql
{{
  config(
    materialized='incremental',
    unique_key='customer_key',
    file_format='iceberg'
  )
}}

SELECT
    customer_key,
    customer_id,
    email
FROM {{ ref('stg_customers') }}

{% if is_incremental() %}
    WHERE valid_from > (SELECT MAX(valid_from) FROM {{ this }})
{% endif %}
```

**DBT runs SQL via Trino** → Trino creates Iceberg table in MinIO

## Performance Tuning

### 1. Partition Tables Appropriately

```sql
-- Good: Partition by date for time-series data
CREATE TABLE events (...)
WITH (partitioning = ARRAY['day(event_time)']);

-- Bad: Too many partitions
WITH (partitioning = ARRAY['hour(event_time)']);  -- Creates 24*365 = 8,760 partitions/year
```

### 2. Use Columnar Format

```sql
-- PARQUET recommended (columnar, compressed)
WITH (format = 'PARQUET');

-- ORC also good
WITH (format = 'ORC');

-- AVRO not recommended for analytics (row-based)
```

### 3. Collect Statistics

```sql
-- Analyze table for query optimization
ANALYZE lakehouse.analytics.dim_customer;
```

### 4. Scale Workers

```yaml
# values.yaml
worker:
  replicas: 4  # Increase for more parallelism
```

### 5. Tune Worker Memory

```yaml
worker:
  jvm:
    maxHeapSize: "8G"
  config:
    query.max-memory-per-node: "4GB"
```

## Troubleshooting

### Cannot Connect to MinIO S3

**Check**:
```bash
kubectl exec -n lakehouse $TRINO_POD -- curl -I http://minio:3900
```

**Verify** catalog configuration has correct endpoint and credentials.

### Query Fails: "Table not found"

**Check catalog**:
```sql
SHOW CATALOGS;
SHOW SCHEMAS FROM iceberg;
SHOW TABLES FROM iceberg.lakehouse.analytics;
```

**Verify** Hive Metastore has table metadata.

### Query Slow

**Check query plan**:
```sql
EXPLAIN SELECT * FROM dim_customer WHERE is_current = TRUE;
```

**Look for**:
- Full table scans (add partitioning/indexes)
- Large shuffles (optimize join order)
- Many small files (run compaction)

## Best Practices

### 1. Use Connection Pooling

For applications making frequent queries, use connection pooling (JDBC pooling, SQLAlchemy pool).

### 2. Limit Result Sets

```sql
-- Always use LIMIT for exploratory queries
SELECT * FROM large_table LIMIT 100;
```

### 3. Monitor Query Performance

**Trino UI** shows:
- Query execution time
- Data processed
- Worker utilization

### 4. Use Materialized Views

```sql
CREATE MATERIALIZED VIEW daily_revenue AS
SELECT
    DATE(order_date) as date,
    SUM(amount) as total_revenue
FROM fct_orders
GROUP BY DATE(order_date);
```

### 5. Separate Read and Write Workloads

- Use coordinator for writes (DDL)
- Scale workers for reads (queries)

## Integration with Other Components

- **[Apache Iceberg](apache-iceberg.md)**: Trino's primary table format
- **[MinIO](minio.md)**: Storage backend for Iceberg tables
- **[DBT](dbt.md)**: Executes transformations via Trino
- **[Hive Metastore](hive-metastore.md)**: Catalogs Iceberg tables
- **[Dagster](dagster.md)**: Orchestrates Trino/DBT jobs

## References

- [Official Trino Documentation](https://trino.io/docs/current/)
- [Trino Iceberg Connector](https://trino.io/docs/current/connector/iceberg.html)
- [Trino SQL Reference](https://trino.io/docs/current/sql.html)
- [Trino Performance Tuning](https://trino.io/docs/current/admin/tuning.html)
- Project Setup Guide: [SETUP_GUIDE.md](../../SETUP_GUIDE.md)
