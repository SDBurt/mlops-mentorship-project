# Medallion Architecture - Data Quality Layers

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established Medallion Architecture patterns and this project's architecture, please verify critical details against best practices for your specific use cases.

## Overview

Medallion Architecture is a data design pattern that organizes data into three progressive quality layers: Bronze (raw), Silver (cleaned), and Gold (business-ready). Each layer incrementally improves data quality, transforming raw ingested data into trusted analytics assets.

In this lakehouse platform, [Airbyte](airbyte.md) populates Bronze, [DBT](dbt.md) transforms Bronze → Silver → Gold, and [Trino](trino.md) queries all layers via [Apache Iceberg](apache-iceberg.md) tables in [MinIO](minio.md) S3.

## Why Medallion Architecture?

**Progressive Quality**: Data quality improves layer by layer - failures isolated to single layer.

**Clear Ownership**: Bronze (data engineers), Silver (analytics engineers), Gold (analysts/data scientists).

**Debugging**: Issues traced back to source - inspect Bronze raw data vs Silver transformations.

**Reusability**: Silver dimensions reused across multiple Gold facts.

**Performance**: Bronze (append-only, fast writes) vs Gold (denormalized, fast queries).

## Three Layers

### Bronze Layer (Raw / Staging)

**Purpose**: Store raw, unmodified data from sources

**Characteristics**:
- **Minimal transformation**: Type casting, column renaming only
- **Append-only**: Never delete/update (preserve history)
- **High velocity**: Fast writes, no complex logic
- **Materialized as**: Views (no storage overhead)
- **Schema**: Often mirrors source schema exactly

**Example - Bronze staging view**:
```sql
-- models/bronze/stg_customers.sql
{{ config(materialized='view') }}

SELECT
    customer_id::BIGINT as customer_id,
    email::VARCHAR as email,
    first_name::VARCHAR as first_name,
    last_name::VARCHAR as last_name,
    CAST(updated_at AS TIMESTAMP) as updated_at,
    _airbyte_extracted_at as extracted_at
FROM {{ source('raw', 'postgres_customers') }}
```

**Key principle**: If source data is bad, Bronze is bad - faithfully represent source.

### Silver Layer (Cleaned / Conformed)

**Purpose**: Clean, deduplicate, and conform data to business rules

**Characteristics**:
- **Data quality**: Remove nulls, fix types, deduplicate
- **Business logic**: Apply transformations, lookups, enrichment
- **SCD Type 2**: Track historical changes (slowly changing dimensions)
- **Materialized as**: Incremental Iceberg tables
- **Schema**: Business-friendly column names, standardized types

**Example - Silver dimension**:
```sql
-- models/silver/dim_customer.sql
{{
  config(
    materialized='incremental',
    unique_key='customer_key',
    file_format='iceberg',
    partition_by=['month(valid_from)']
  )
}}

WITH source AS (
    SELECT * FROM {{ ref('stg_customers') }}
    {% if is_incremental() %}
    WHERE updated_at > (SELECT MAX(valid_from) FROM {{ this }})
    {% endif %}
),

-- Deduplicate
deduped AS (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY updated_at DESC) as rn
    FROM source
),

-- Clean and validate
cleaned AS (
    SELECT
        customer_id,
        LOWER(TRIM(email)) as email,  -- Standardize email
        INITCAP(TRIM(first_name)) as first_name,  -- Proper case
        INITCAP(TRIM(last_name)) as last_name,
        updated_at
    FROM deduped
    WHERE rn = 1
      AND email IS NOT NULL  -- Data quality: require email
      AND email LIKE '%@%'   -- Basic validation
)

SELECT
    {{ dbt_utils.surrogate_key(['customer_id', 'updated_at']) }} as customer_key,
    customer_id,
    email,
    first_name,
    last_name,
    updated_at as valid_from,
    NULL::TIMESTAMP as valid_to,
    TRUE as is_current
FROM cleaned
```

**Key principle**: One source of truth - Silver is authoritative cleaned data.

### Gold Layer (Business / Analytics)

**Purpose**: Business-ready aggregated data for analytics/reporting

**Characteristics**:
- **Star schema**: Fact tables + dimension references
- **Denormalized**: Optimized for query performance
- **Aggregated**: Pre-calculated metrics
- **Materialized as**: Incremental Iceberg tables
- **Schema**: Business-friendly, report-ready

**Example - Gold fact table**:
```sql
-- models/gold/fct_orders.sql
{{
  config(
    materialized='incremental',
    unique_key='order_key',
    file_format='iceberg',
    partition_by=['date(order_date)']
  )
}}

SELECT
    {{ dbt_utils.surrogate_key(['o.order_id']) }} as order_key,
    c.customer_key,
    p.product_key,
    d.date_key,
    o.order_id,
    o.quantity,
    o.unit_price,
    o.quantity * o.unit_price as total_amount,
    o.order_date,
    -- Denormalized for reporting
    c.email as customer_email,
    c.first_name || ' ' || c.last_name as customer_name,
    p.product_name,
    p.category as product_category
FROM {{ ref('stg_orders') }} o
LEFT JOIN {{ ref('dim_customer') }} c
    ON o.customer_id = c.customer_id
    AND c.is_current = TRUE
LEFT JOIN {{ ref('dim_product') }} p
    ON o.product_id = p.product_id
    AND p.is_current = TRUE
LEFT JOIN {{ ref('dim_date') }} d
    ON DATE(o.order_date) = d.date

{% if is_incremental() %}
WHERE o.order_date > (SELECT MAX(order_date) FROM {{ this }})
{% endif %}
```

**Key principle**: Optimized for consumption - fast queries, no joins required.

## Data Flow

```
[Airbyte] extracts from sources
    ↓
s3://lakehouse/raw/postgres_customers/  (Raw Parquet files)
    ↓
[DBT Bronze] creates view over raw data
    ↓
bronze.stg_customers  (View - minimal transformation)
    ↓
[DBT Silver] cleans and validates
    ↓
silver.dim_customer  (Iceberg table - cleaned dimension)
    ↓
[DBT Gold] joins and aggregates
    ↓
gold.fct_orders  (Iceberg table - star schema fact)
    ↓
[BI Tools / Analysts] query Gold layer
```

## Layer Guidelines

### Bronze Guidelines

**DO**:
- Keep raw data unchanged
- Cast types for consistency
- Rename columns to snake_case
- Add extraction timestamps
- Store as views (no duplication)

**DON'T**:
- Filter rows (keep all data)
- Apply business logic
- Deduplicate
- Join tables

### Silver Guidelines

**DO**:
- Deduplicate records
- Validate data quality
- Apply business rules
- Track history (SCD Type 2)
- Use incremental models

**DON'T**:
- Aggregate data
- Denormalize for performance
- Create report-specific tables

### Gold Guidelines

**DO**:
- Create star schemas (facts + dimensions)
- Denormalize for query performance
- Pre-calculate metrics
- Partition by common query filters

**DON'T**:
- Store raw/uncleaned data
- Complex transformations (do in Silver)

## Alternative Naming Conventions

**Databricks style**:
- Bronze = Raw
- Silver = Enriched
- Gold = Curated

**Data Vault style**:
- Bronze = Staging
- Silver = Core (Hubs/Links/Satellites)
- Gold = Marts

**This project uses**: Bronze/Silver/Gold (most common)

## Project Structure

```
transformations/dbt/models/
├── sources.yml              # Raw data sources (Airbyte output)
├── bronze/                  # Staging views
│   ├── stg_customers.sql
│   ├── stg_orders.sql
│   └── stg_products.sql
├── silver/                  # Cleaned dimensions
│   ├── dim_customer.sql
│   ├── dim_product.sql
│   └── dim_date.sql
└── gold/                    # Business facts
    ├── fct_orders.sql
    └── fct_daily_revenue.sql
```

## Performance Considerations

### Bronze Layer

**Fast writes**:
- Views only (no materialization)
- No transformations

### Silver Layer

**Incremental processing**:
- Only process new/changed records
- Partition by date for pruning
```sql
{% if is_incremental() %}
WHERE updated_at > (SELECT MAX(valid_from) FROM {{ this }})
{% endif %}
```

### Gold Layer

**Query optimization**:
- Partition by report filter columns
- Denormalize to avoid joins
- Pre-aggregate where possible

**Example - Pre-aggregated metrics**:
```sql
-- models/gold/fct_daily_revenue.sql
SELECT
    date_key,
    product_category,
    SUM(total_amount) as daily_revenue,
    COUNT(DISTINCT customer_key) as unique_customers,
    COUNT(order_key) as order_count
FROM {{ ref('fct_orders') }}
GROUP BY date_key, product_category
```

## Best Practices

### 1. Never Skip Layers

**Bad**:
```sql
-- Bronze → Gold (skipping Silver)
-- Hard to debug, poor data quality
```

**Good**:
```sql
-- Bronze → Silver → Gold
-- Clear progression, each layer testable
```

### 2. Test Each Layer

```yaml
# models/schema.yml
models:
  - name: dim_customer
    tests:
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns:
            - customer_id
            - valid_from
    columns:
      - name: email
        tests:
          - not_null
          - unique:
              where: "is_current = TRUE"
```

### 3. Document Layer Purpose

```sql
-- models/silver/dim_customer.sql
/*
  Silver Layer: dim_customer

  Purpose: Cleaned and validated customer dimension with SCD Type 2 history.

  Transformations:
  - Deduplicate by customer_id
  - Standardize email to lowercase
  - Remove invalid emails (no @ symbol)
  - Track historical changes via valid_from/valid_to

  Tests:
  - Unique customer_key
  - Non-null email
  - Valid email format
*/
```

### 4. Use Consistent Naming

- **Bronze**: `stg_<entity>` (staging)
- **Silver**: `dim_<entity>` (dimension) or `int_<entity>` (intermediate)
- **Gold**: `fct_<entity>` (fact) or `rpt_<entity>` (report)

### 5. Monitor Data Quality by Layer

**Metrics to track**:
- Bronze: Record count, extraction lag
- Silver: Duplicate rate, null rate, validation failures
- Gold: Row count, query performance

## Integration with Other Components

- **[DBT](dbt.md)**: Implements Bronze → Silver → Gold transformations
- **[Airbyte](airbyte.md)**: Populates Bronze raw data
- **[Trino](trino.md)**: Queries all three layers
- **[Apache Iceberg](apache-iceberg.md)**: Stores Silver/Gold as Iceberg tables
- **[Star Schema](star-schema.md)**: Gold layer uses star schema design

## References

- [Databricks Medallion Architecture](https://www.databricks.com/glossary/medallion-architecture)
- [DBT Best Practices - Staging Models](https://docs.getdbt.com/best-practices/how-we-structure/2-staging)
- [Data Mesh - Domain-Oriented Ownership](https://martinfowler.com/articles/data-mesh-principles.html)
- Project Setup Guide: [SETUP_GUIDE.md](../../SETUP_GUIDE.md)
