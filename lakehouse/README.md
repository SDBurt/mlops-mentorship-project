# Lakehouse Architecture

This directory documents the lakehouse data structure, table schemas, and conventions for organizing data in Apache Iceberg format.

## Overview

Our lakehouse implements a **medallion architecture** with three layers:
- **Bronze (raw/)**: Raw ingested data, minimal transformations
- **Silver (processed/)**: Cleaned, validated, and enriched data
- **Gold (analytics/)**: Business-level aggregates and metrics

All tables use **Apache Iceberg** format with **Parquet** storage for ACID transactions, schema evolution, and time travel capabilities.

## Storage Layout

### S3 Bucket Structure

```
s3://datalake/
├── raw/                           # Bronze layer
│   ├── ecommerce/
│   │   ├── users/
│   │   │   └── metadata/
│   │   │       ├── v1.metadata.json
│   │   │       └── snap-*.avro
│   │   ├── orders/
│   │   └── products/
│   └── analytics/
│       ├── web_events/
│       └── mobile_events/
│
├── processed/                     # Silver layer
│   ├── core/
│   │   ├── dim_users/
│   │   ├── dim_products/
│   │   └── fct_orders/
│   └── domain/
│       ├── customer_360/
│       └── inventory/
│
├── analytics/                     # Gold layer
│   ├── metrics/
│   │   ├── daily_revenue/
│   │   └── user_retention/
│   └── reports/
│       ├── executive_dashboard/
│       └── ops_dashboard/
│
└── ml/                            # ML artifacts
    ├── features/
    │   └── user_features/
    ├── training_data/
    └── models/
```

## Naming Conventions

### Database and Schema Names

Format: `<layer>.<domain>`

Examples:
- `raw.ecommerce`
- `processed.core`
- `analytics.metrics`
- `ml.features`

### Table Names

Format: `<type>_<entity>_<description>`

**Types:**
- `dim_` - Dimension table (entities like users, products)
- `fct_` - Fact table (events, transactions)
- `agg_` - Aggregated metrics
- `stg_` - Staging (temporary, intermediate)

**Examples:**
- `dim_users`
- `fct_orders`
- `fct_clickstream_events`
- `agg_daily_revenue`
- `agg_user_retention_cohorts`

### Column Names

- Use lowercase with underscores: `user_id`, `order_date`
- Prefix boolean columns with `is_` or `has_`: `is_active`, `has_subscription`
- Suffix timestamps with `_at`: `created_at`, `updated_at`
- Suffix dates with `_date`: `order_date`, `signup_date`

## Table Schemas

### Bronze Layer (Raw)

Raw tables mirror source systems with minimal transformations:

```sql
CREATE TABLE raw.ecommerce.users (
    user_id STRING,
    email STRING,
    first_name STRING,
    last_name STRING,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    _airbyte_extracted_at TIMESTAMP,
    _airbyte_raw_id STRING
)
USING iceberg
PARTITIONED BY (days(created_at))
TBLPROPERTIES (
    'format-version' = '2',
    'write.parquet.compression-codec' = 'snappy'
);
```

**Conventions:**
- Keep all source columns
- Add metadata columns (`_airbyte_*`, `_extracted_at`)
- Partition by date for incremental processing
- No data cleaning or validation

### Silver Layer (Processed)

Cleaned, validated, and enriched data:

```sql
CREATE TABLE processed.core.dim_users (
    user_id STRING NOT NULL,
    email STRING NOT NULL,
    first_name STRING,
    last_name STRING,
    full_name STRING,
    is_active BOOLEAN,
    signup_date DATE,
    country_code STRING,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    _dbt_updated_at TIMESTAMP
)
USING iceberg
PARTITIONED BY (months(signup_date))
TBLPROPERTIES (
    'format-version' = '2',
    'write.metadata.compression-codec' = 'gzip'
);
```

**Conventions:**
- Add NOT NULL constraints
- Standardize data types
- Add derived columns (e.g., `full_name`)
- Remove technical metadata columns
- Appropriate partitioning for query patterns
- Add data lineage columns (`_dbt_updated_at`)

### Gold Layer (Analytics)

Business-ready aggregates and metrics:

```sql
CREATE TABLE analytics.metrics.daily_revenue (
    metric_date DATE NOT NULL,
    region STRING,
    product_category STRING,
    total_orders BIGINT,
    total_revenue DECIMAL(12,2),
    avg_order_value DECIMAL(10,2),
    unique_customers BIGINT,
    created_at TIMESTAMP NOT NULL
)
USING iceberg
PARTITIONED BY (months(metric_date))
TBLPROPERTIES (
    'format-version' = '2'
);
```

**Conventions:**
- Pre-aggregated for dashboard performance
- Denormalized for easy querying
- Clear metric definitions
- Document business logic

## Partitioning Strategies

### Time-Based Partitioning

**Daily:**
```sql
PARTITIONED BY (days(event_timestamp))
```
Use for: High-volume event data with daily queries

**Monthly:**
```sql
PARTITIONED BY (months(order_date))
```
Use for: Moderate-volume transactional data

**Yearly:**
```sql
PARTITIONED BY (years(created_at))
```
Use for: Low-volume historical data

### Multi-Column Partitioning

```sql
PARTITIONED BY (
    region,
    days(event_timestamp)
)
```
Use for: Data with clear geographic or categorical segments

## Table Properties

### Standard Properties

```sql
TBLPROPERTIES (
    'format-version' = '2',                          -- Use Iceberg V2
    'write.parquet.compression-codec' = 'snappy',    -- Fast compression
    'write.metadata.compression-codec' = 'gzip',     -- Metadata compression
    'write.target-file-size-bytes' = '536870912',    -- 512MB target files
    'commit.retry.num-retries' = '3'                 -- Retry on conflicts
)
```

### Performance Tuning

```sql
TBLPROPERTIES (
    'write.distribution-mode' = 'hash',              -- Distribute by hash
    'write.delete.mode' = 'merge-on-read',          -- Fast deletes
    'write.update.mode' = 'merge-on-read',          -- Fast updates
    'read.split.target-size' = '134217728'          -- 128MB read splits
)
```

## Schema Evolution

Iceberg supports safe schema changes:

```sql
-- Add column (safe)
ALTER TABLE processed.core.dim_users
ADD COLUMN phone_number STRING;

-- Rename column (safe)
ALTER TABLE processed.core.dim_users
RENAME COLUMN old_name TO new_name;

-- Change column type (careful!)
ALTER TABLE processed.core.dim_users
ALTER COLUMN email TYPE VARCHAR(320);

-- Drop column (safe, data remains)
ALTER TABLE processed.core.dim_users
DROP COLUMN deprecated_field;
```

**Best Practices:**
- Test schema changes in dev first
- Document breaking changes
- Use column comments for clarity
- Version control schema DDL

## Time Travel

Query historical data:

```sql
-- Query as of timestamp
SELECT * FROM processed.core.dim_users
FOR SYSTEM_TIME AS OF TIMESTAMP '2024-01-01 00:00:00';

-- Query specific snapshot
SELECT * FROM processed.core.dim_users
FOR SYSTEM_VERSION AS OF 123456789;

-- View snapshot history
SELECT * FROM processed.core.dim_users.snapshots
ORDER BY committed_at DESC;

-- Rollback to previous snapshot
CALL iceberg.system.rollback_to_snapshot(
    'processed.core.dim_users',
    123456789
);
```

## Table Maintenance

### Compact Small Files

Run regularly to optimize query performance:

```sql
CALL iceberg.system.rewrite_data_files(
    table => 'processed.core.dim_users',
    strategy => 'binpack',
    options => map('target-file-size-bytes', '536870912')
);
```

### Expire Old Snapshots

Clean up old metadata:

```sql
CALL iceberg.system.expire_snapshots(
    table => 'processed.core.dim_users',
    older_than => TIMESTAMP '2024-01-01 00:00:00',
    retain_last => 10
);
```

### Remove Orphan Files

Delete unreferenced data files:

```sql
CALL iceberg.system.remove_orphan_files(
    table => 'processed.core.dim_users',
    older_than => TIMESTAMP '2024-01-01 00:00:00'
);
```

## Data Quality Standards

### Required Columns

All tables must have:
- Primary key(s) with NOT NULL constraint
- `created_at` timestamp
- `updated_at` timestamp (for mutable tables)

### Data Types

**Preferred Types:**
- String IDs: `STRING` (not `VARCHAR`)
- Timestamps: `TIMESTAMP` (with timezone)
- Decimals: `DECIMAL(p,s)` for money
- Booleans: `BOOLEAN` (not 0/1 integers)

**Avoid:**
- `TEXT` (use `STRING`)
- `FLOAT` for money (use `DECIMAL`)
- String timestamps (use `TIMESTAMP`)

### Null Handling

- Mark columns as `NOT NULL` where possible
- Use `COALESCE()` for defaults in queries
- Document nullable columns

## Documentation

### Table Comments

```sql
COMMENT ON TABLE processed.core.dim_users IS
    'Customer dimension with enriched user attributes. Updated daily via DBT.';

COMMENT ON COLUMN processed.core.dim_users.user_id IS
    'Unique identifier for user. Maps to users.id in source system.';
```

### Catalog Documentation

Maintain in version control:

```yaml
# lakehouse/catalog.yml
tables:
  - name: processed.core.dim_users
    description: Customer dimension
    owner: data-team
    tags: [pii, gdpr]
    columns:
      - name: user_id
        description: Primary key
        type: STRING
        nullable: false
```

## Access Patterns

### OLAP Queries (Trino)

Optimized for:
- Column scans
- Aggregations
- Time-range filters
- Joins on partitioned columns

### Streaming Reads

Use Iceberg incremental reads:
```python
# Read only new data since last snapshot
df = spark.read \
    .format("iceberg") \
    .option("start-snapshot-id", last_snapshot) \
    .load("processed.core.fct_events")
```

## Security

### Row-Level Security

Implement in Trino:
```sql
-- View with row filtering
CREATE VIEW processed.core.dim_users_filtered AS
SELECT * FROM processed.core.dim_users
WHERE region = CURRENT_USER_REGION();
```

### Column Masking

For PII/sensitive data:
```sql
-- Mask email for non-privileged users
CREATE VIEW processed.core.dim_users_public AS
SELECT
    user_id,
    CASE WHEN has_pii_access()
        THEN email
        ELSE '***@***'
    END AS email,
    first_name,
    last_name
FROM processed.core.dim_users;
```

## Migration from Bronze to Silver

1. Create Iceberg table in Silver layer
2. Run DBT transformation to populate
3. Validate data quality
4. Update downstream dependencies
5. Deprecate Bronze table (if no longer needed)

## Resources

- [Apache Iceberg Spec](https://iceberg.apache.org/spec/)
- [Iceberg Table Maintenance](https://iceberg.apache.org/docs/latest/maintenance/)
- [Medallion Architecture](https://www.databricks.com/glossary/medallion-architecture)
- [Parquet Format](https://parquet.apache.org/docs/)

## Status

This is a living document that evolves with the platform. Conventions should be updated as we learn best practices.
