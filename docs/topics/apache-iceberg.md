# Apache Iceberg - Open Table Format

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established Apache Iceberg concepts and this project's architecture, please verify critical details against official Apache Iceberg documentation and your specific use cases.

## Overview

Apache Iceberg is an open table format for huge analytic datasets. It brings database-like features (ACID transactions, schema evolution, time travel) to data lake storage systems like [Garage](garage.md) S3.

Instead of managing raw Parquet files directly, Iceberg provides a metadata layer that tracks files, schemas, partitions, and versions. This enables reliable, scalable analytics over petabyte-scale datasets.

In this lakehouse platform, Iceberg tables store all data: raw ingestion from [Airbyte](airbyte.md), transformed layers from [DBT](dbt.md), and final analytics tables queried by [Trino](trino.md).

## Why Iceberg for This Platform?

**ACID Transactions**: Multiple writers can safely modify tables concurrently without corruption.

**Schema Evolution**: Add, drop, or rename columns without rewriting data files.

**Time Travel**: Query table state at any point in history (snapshots).

**Hidden Partitioning**: Partition tables transparently - users query without knowing partition structure.

**Fast Queries**: Metadata pruning skips irrelevant files, speeding up queries dramatically.

**Industry Standard**: Supported by Trino, Spark, Flink, DBT - portable across engines.

## Key Concepts

### 1. Table Metadata Layer

**What it is**: Iceberg adds a metadata layer on top of data files (Parquet, ORC, Avro).

**Traditional Data Lake** (no Iceberg):
```
s3://lakehouse/customers/
├── part-0001.parquet
├── part-0002.parquet
├── part-0003.parquet
└── part-0004.parquet
```

**Problem**: No schema tracking, no transaction guarantees, no version history.

**With Iceberg**:
```
s3://lakehouse/warehouse/customers/
├── data/
│   ├── part-0001.parquet
│   ├── part-0002.parquet
│   ├── part-0003.parquet
│   └── part-0004.parquet
└── metadata/
    ├── v1.metadata.json      # Schema, partition spec
    ├── v2.metadata.json      # Updated schema
    ├── snap-123.avro         # Snapshot manifest list
    ├── manifest-001.avro     # File list for snapshot 123
    └── manifest-002.avro     # File list for snapshot 124
```

**Metadata files**:
- **metadata.json**: Table schema, partition spec, snapshot list
- **manifest-list.avro**: List of manifest files for a snapshot
- **manifest.avro**: List of data files with statistics (row count, column min/max)

**Query flow**:
1. Read `metadata.json` to get current snapshot
2. Read manifest list for snapshot
3. Read manifests to find relevant data files
4. Prune files based on predicate pushdown
5. Read only relevant Parquet files

**Result**: Query only scans necessary files, not entire dataset.

### 2. ACID Transactions

**What it is**: Iceberg guarantees atomicity, consistency, isolation, and durability for table operations.

**Without Iceberg**:
```sql
-- Scenario: Add new data to table
-- Writer 1 writes part-0005.parquet
-- Writer 2 writes part-0006.parquet
-- Reader queries mid-write → sees incomplete data!
```

**With Iceberg**:
```sql
-- Writer 1 creates snapshot 124 with part-0005.parquet
-- Writer 2 creates snapshot 125 with part-0006.parquet
-- Readers always see complete snapshots (123, 124, or 125)
-- No partial reads!
```

**Concurrency control**:
- **Optimistic concurrency**: Each writer creates new snapshot
- **Atomic commit**: New metadata file written, then pointer updated atomically
- **Retry on conflict**: If two writers conflict, one retries with newer base

**Example - DBT Incremental Model**:
```sql
-- DBT run 1: Adds 1000 rows, creates snapshot 124
-- DBT run 2: Adds 1000 rows, creates snapshot 125
-- Trino query during DBT run 2: Reads snapshot 124 (consistent)
-- Trino query after DBT run 2: Reads snapshot 125 (new data)
```

**Benefit**: No locking required - multiple jobs can write concurrently safely.

### 3. Schema Evolution

**What it is**: Change table schema without rewriting data files.

**Supported operations**:
- **Add column**: New column added with default value (no rewrite)
- **Drop column**: Column hidden from queries (files not rewritten)
- **Rename column**: Metadata-only change (no data movement)
- **Widen type**: INT → BIGINT, FLOAT → DOUBLE (safe, no rewrite)
- **Reorder columns**: Change column order (metadata-only)

**Example - Add Column**:
```sql
-- Initial schema
CREATE TABLE customers (
    id BIGINT,
    name VARCHAR,
    email VARCHAR
);

-- Insert 1 million rows...

-- Add column (instant - no data rewrite!)
ALTER TABLE customers ADD COLUMN phone VARCHAR;

-- Old files: [id, name, email]
-- New files: [id, name, email, phone]
-- Queries see 'phone' as NULL for old files
```

**Under the hood**:
- Old Parquet files don't have `phone` column
- Iceberg metadata tracks schema version per file
- Query engine fills NULL for missing columns
- New writes include `phone` column

**Benefit**: Schema changes take seconds, not hours (no data rewrite).

### 4. Time Travel

**What it is**: Query table state at previous snapshots.

**Use cases**:
- Debug data issues ("What did the table look like yesterday?")
- Reproduce reports ("Re-run report with last week's data")
- Rollback mistakes ("Undo accidental delete")

**Example**:
```sql
-- Current table state (snapshot 125, 10:00 AM today)
SELECT COUNT(*) FROM customers;
-- Result: 10,000 rows

-- Time travel to yesterday (snapshot 120, 10:00 AM yesterday)
SELECT COUNT(*) FROM customers FOR SYSTEM_VERSION AS OF 120;
-- Result: 9,500 rows

-- Time travel by timestamp
SELECT COUNT(*) FROM customers FOR SYSTEM_TIME AS OF TIMESTAMP '2025-01-20 10:00:00';
-- Result: 9,500 rows
```

**How it works**:
- Every table change creates new snapshot
- Old snapshots retained (configurable retention period)
- Metadata files track snapshot history
- Data files shared across snapshots (no duplication)

**Cleanup**:
```sql
-- Expire old snapshots (free up metadata files)
CALL iceberg.system.expire_snapshots(
  table => 'customers',
  older_than => TIMESTAMP '2025-01-15 00:00:00',
  retain_last => 10  -- Keep at least 10 snapshots
);
```

### 5. Hidden Partitioning

**What it is**: Partition tables without exposing partition columns in queries.

**Traditional partitioning**:
```sql
-- Partition by date
CREATE TABLE orders (
    order_id BIGINT,
    customer_id BIGINT,
    order_date DATE,
    amount DECIMAL
) PARTITIONED BY (order_date);

-- Query must include partition column
SELECT * FROM orders
WHERE order_date = DATE '2025-01-20';  -- ✓ Fast (partition pruning)

SELECT * FROM orders
WHERE order_id = 12345;  -- ✗ Slow (full table scan)
```

**Iceberg hidden partitioning**:
```sql
-- Partition by month(order_date)
CREATE TABLE orders (
    order_id BIGINT,
    customer_id BIGINT,
    order_date DATE,
    amount DECIMAL
)
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['month(order_date)']  -- Hidden partition
);

-- Query any column - Iceberg automatically prunes
SELECT * FROM orders
WHERE order_date = DATE '2025-01-20';  -- ✓ Fast (prunes to January partition)

SELECT * FROM orders
WHERE order_date BETWEEN DATE '2025-01-15' AND DATE '2025-02-10';  -- ✓ Prunes to Jan + Feb
```

**Partition transforms**:
- `year(timestamp_col)` - Partition by year
- `month(timestamp_col)` - Partition by month
- `day(timestamp_col)` - Partition by day
- `hour(timestamp_col)` - Partition by hour
- `bucket(N, col)` - Hash partition into N buckets
- `truncate(length, col)` - Truncate strings

**Benefit**: Users query naturally - Iceberg handles partition pruning automatically.

### 6. Incremental Reads

**What it is**: Read only new data added since last query (for streaming/incremental processing).

**Use case**: DBT incremental models

**Example**:
```sql
-- Last DBT run processed up to snapshot 120

-- Current state: snapshot 125
-- DBT incremental query: "Give me only new rows since snapshot 120"
SELECT *
FROM customers
FOR SYSTEM_VERSION AS OF 125
WHERE _iceberg_snapshot_id > 120;
```

**In DBT**:
```sql
{{
  config(
    materialized='incremental',
    unique_key='customer_id',
    incremental_strategy='merge'
  )
}}

SELECT
    customer_id,
    email,
    updated_at
FROM {{ source('raw', 'customers') }}

{% if is_incremental() %}
    -- Only process new snapshots
    WHERE _iceberg_snapshot_id > (SELECT MAX(_iceberg_snapshot_id) FROM {{ this }})
{% endif %}
```

**Benefit**: Process only changed data, not entire table (massive performance gain).

## Iceberg in This Platform

### Table Storage Location

All Iceberg tables stored in [Garage](garage.md) S3:

```
s3://lakehouse/warehouse/
├── analytics/              # Database: analytics
│   ├── dim_customer/       # Table: dim_customer
│   │   ├── data/
│   │   │   ├── part-0001.parquet
│   │   │   └── part-0002.parquet
│   │   └── metadata/
│   │       ├── v1.metadata.json
│   │       └── snap-001.avro
│   └── fct_orders/         # Table: fct_orders
│       ├── data/
│       └── metadata/
└── raw/                    # Database: raw
    └── customers/          # Table: customers
        ├── data/
        └── metadata/
```

### Catalog Integration

Iceberg tables managed by catalog (metadata store):

**Phase 2** (Current): [Hive Metastore](hive-metastore.md)
```sql
-- Trino configuration
iceberg.catalog.type=hive_metastore
hive.metastore.uri=thrift://hive-metastore.database.svc.cluster.local:9083
```

**Phase 3** (Planned): [Polaris REST Catalog](polaris-rest-catalog.md)
```sql
-- Trino configuration
iceberg.catalog.type=rest
iceberg.rest.uri=http://polaris.governance.svc.cluster.local:8181
```

### Creating Iceberg Tables

**Via Trino**:
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

**Via DBT** (materializes as Iceberg table):
```sql
{{
  config(
    materialized='incremental',
    unique_key='customer_key',
    file_format='iceberg',
    incremental_strategy='merge',
    partition_by=['month(valid_from)']
  )
}}

SELECT
    {{ dbt_utils.surrogate_key(['customer_id', 'valid_from']) }} as customer_key,
    customer_id,
    email,
    first_name,
    last_name,
    updated_at as valid_from,
    NULL as valid_to,
    TRUE as is_current
FROM {{ source('raw', 'customers') }}
```

### Querying Iceberg Tables

**Via Trino**:
```sql
-- Regular query
SELECT * FROM lakehouse.analytics.dim_customer
WHERE is_current = TRUE;

-- Time travel
SELECT * FROM lakehouse.analytics.dim_customer
FOR SYSTEM_VERSION AS OF 100;

-- Metadata queries
SELECT snapshot_id, committed_at, operation, summary
FROM "lakehouse.analytics.dim_customer$snapshots"
ORDER BY committed_at DESC
LIMIT 10;
```

**Via DBT**:
```sql
-- DBT references Iceberg tables seamlessly
SELECT
    c.customer_key,
    c.email,
    COUNT(o.order_id) as total_orders
FROM {{ ref('dim_customer') }} c
LEFT JOIN {{ ref('fct_orders') }} o ON c.customer_key = o.customer_key
GROUP BY c.customer_key, c.email
```

## Best Practices

### 1. Choose Appropriate Partitioning

**Good** (partitions reduce query time):
```sql
-- Large table, commonly filtered by date
CREATE TABLE events (...) WITH (
    partitioning = ARRAY['day(event_time)']
);

-- Query benefits from partition pruning
SELECT * FROM events WHERE event_time = DATE '2025-01-20';  -- Only scans 1 day
```

**Bad** (too many partitions):
```sql
-- Creates millions of tiny partitions
WITH (partitioning = ARRAY['second(event_time)'])  -- Don't do this!
```

**Rule of thumb**:
- **Few partitions** (<1000): Good for selective queries
- **Many partitions** (>10,000): Metadata overhead, slow planning
- **Partition size**: Target 100MB-1GB per partition

### 2. Compact Small Files Regularly

**Problem**: Many small files slow down queries

```bash
# Check file count
SELECT COUNT(*) FROM "lakehouse.analytics.dim_customer$files";
# Result: 10,000 files (bad!)
```

**Solution**: Compact small files into larger ones

```sql
-- Trino: Compact files
CALL iceberg.system.rewrite_data_files(
  table => 'lakehouse.analytics.dim_customer',
  options => MAP(
    ARRAY['target_file_size_mb'],
    ARRAY['512']  -- Target 512MB files
  )
);
```

**Schedule compaction** (e.g., nightly in Dagster).

### 3. Expire Old Snapshots

**Problem**: Metadata accumulates over time

```sql
-- Check snapshot count
SELECT COUNT(*) FROM "lakehouse.analytics.dim_customer$snapshots";
# Result: 1,000 snapshots (keep only recent)
```

**Solution**: Expire old snapshots

```sql
CALL iceberg.system.expire_snapshots(
  table => 'lakehouse.analytics.dim_customer',
  older_than => TIMESTAMP '2025-01-15 00:00:00',
  retain_last => 100  -- Keep at least 100 snapshots
);
```

### 4. Use Hidden Partitioning

**Good**:
```sql
CREATE TABLE orders (...) WITH (
    partitioning = ARRAY['month(order_date)']  -- Hidden
);

-- Users query naturally
SELECT * FROM orders WHERE order_date = '2025-01-20';
```

**Bad**:
```sql
CREATE TABLE orders (...) PARTITIONED BY (order_year, order_month);

-- Users must know partition structure
SELECT * FROM orders WHERE order_year = 2025 AND order_month = 1;
```

### 5. Enable Write Distribution for Concurrency

Prevents file contention when multiple writers work simultaneously:

```sql
CREATE TABLE events (...) WITH (
    partitioning = ARRAY['day(event_time)'],
    write_distribution = 'hash'  -- Distribute writes across workers
);
```

## Integration with Other Components

- **[Garage](garage.md)**: Stores Iceberg data and metadata files
- **[Trino](trino.md)**: Queries Iceberg tables, manages snapshots
- **[DBT](dbt.md)**: Materializes models as Iceberg tables
- **[Hive Metastore](hive-metastore.md)**: Catalogs Iceberg tables (Phase 2)
- **[Polaris REST Catalog](polaris-rest-catalog.md)**: Modern Iceberg catalog (Phase 3)
- **[Medallion Architecture](medallion-architecture.md)**: Bronze/Silver/Gold layers use Iceberg

## References

- [Official Apache Iceberg Documentation](https://iceberg.apache.org/)
- [Iceberg Spec](https://iceberg.apache.org/spec/)
- [Iceberg Table Evolution](https://iceberg.apache.org/evolution/)
- [Iceberg Performance](https://iceberg.apache.org/docs/latest/performance/)
- [Trino Iceberg Connector](https://trino.io/docs/current/connector/iceberg.html)
