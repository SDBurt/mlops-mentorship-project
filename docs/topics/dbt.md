# DBT - Data Build Tool

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established DBT concepts and this project's architecture, please verify critical details against official DBT documentation and your specific use cases.

## Overview

DBT (Data Build Tool) is a transformation tool that enables analytics engineers to transform data using SQL. DBT handles the T in ELT (Extract, Load, Transform) - transforming raw data into clean, modeled tables ready for analytics.

In this lakehouse platform, DBT transforms raw [Airbyte](airbyte.md) data through the [Medallion Architecture](medallion-architecture.md) (Bronze → Silver → Gold), creating [Star Schema](star-schema.md) dimensional models stored as [Apache Iceberg](apache-iceberg.md) tables, orchestrated by [Dagster](dagster.md).

## Why DBT for This Platform?

**SQL-Based**: Write transformations in SQL, not Python - accessible to analysts.

**Modularity**: Models reference each other via `{{ ref() }}` - automatic dependency resolution.

**Testing**: Built-in data quality tests (uniqueness, not null, relationships).

**Documentation**: Auto-generate data dictionary from model descriptions.

**Version Control**: SQL models in Git - standard software development practices.

**Incremental Models**: Process only new/changed data - efficient for large tables.

## Key Concepts

### 1. Models

**What it is**: A SQL SELECT statement that creates a table or view.

**Model file** (`models/silver/dim_customer.sql`):
```sql
{{
  config(
    materialized='incremental',
    unique_key='customer_key',
    file_format='iceberg'
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
FROM {{ ref('stg_customers') }}

{% if is_incremental() %}
    WHERE updated_at > (SELECT MAX(valid_from) FROM {{ this }})
{% endif %}
```

**Materialization types**:
- **view**: Creates SQL view (no physical storage, query on demand)
- **table**: Creates physical table (full refresh each run)
- **incremental**: Appends/merges new data only (efficient for large tables)
- **ephemeral**: CTE only (not materialized, used by other models)

### 2. Sources

**What it is**: Reference to raw tables created by [Airbyte](airbyte.md).

**Source definition** (`models/sources.yml`):
```yaml
version: 2

sources:
  - name: raw
    database: lakehouse
    schema: raw
    tables:
      - name: postgres_customers
        identifier: customers
        description: Raw customer data from Postgres

      - name: postgres_orders
        identifier: orders
```

**Use in models**:
```sql
SELECT * FROM {{ source('raw', 'postgres_customers') }}
-- Compiles to: SELECT * FROM lakehouse.raw.postgres_customers
```

### 3. Refs (References)

**What it is**: Reference to other DBT models - creates dependency graph.

**Example**:
```sql
-- models/bronze/stg_customers.sql (Bronze layer)
SELECT * FROM {{ source('raw', 'postgres_customers') }}

-- models/silver/dim_customer.sql (Silver layer)
SELECT * FROM {{ ref('stg_customers') }}  -- Depends on Bronze

-- models/gold/fct_orders.sql (Gold layer)
SELECT
    o.*,
    c.email
FROM {{ ref('stg_orders') }} o
JOIN {{ ref('dim_customer') }} c  -- Depends on Silver
    ON o.customer_id = c.customer_id
```

**DBT execution order** (automatic):
1. `stg_customers` (no dependencies)
2. `dim_customer` (depends on `stg_customers`)
3. `fct_orders` (depends on `dim_customer`)

### 4. Tests

**Schema tests** (`models/schema.yml`):
```yaml
models:
  - name: dim_customer
    description: Customer dimension with SCD Type 2
    columns:
      - name: customer_key
        description: Surrogate key
        tests:
          - unique
          - not_null

      - name: email
        description: Customer email
        tests:
          - not_null
          - unique:
              where: "is_current = TRUE"

      - name: customer_id
        tests:
          - relationships:
              to: ref('stg_customers')
              field: customer_id
```

**Custom tests** (`tests/assert_no_negative_amounts.sql`):
```sql
SELECT *
FROM {{ ref('fct_orders') }}
WHERE amount < 0
```

**Run tests**:
```bash
dbt test                        # All tests
dbt test --select dim_customer  # Specific model tests
```

### 5. Incremental Models

**Full refresh** (slow for large tables):
```sql
-- Drops and recreates entire table every run
{{ config(materialized='table') }}

SELECT * FROM {{ source('raw', 'events') }}
```

**Incremental** (efficient):
```sql
{{ config(materialized='incremental', unique_key='event_id') }}

SELECT * FROM {{ source('raw', 'events') }}

{% if is_incremental() %}
    -- Only process new events
    WHERE event_time > (SELECT MAX(event_time) FROM {{ this }})
{% endif %}
```

**Incremental strategies**:
- **append**: Add new rows (no updates)
- **merge**: Upsert based on `unique_key` (updates existing rows)
- **delete+insert**: Delete matching rows, insert new ones

### 6. Jinja and Macros

**Jinja templating**:
```sql
{% set payment_methods = ['credit_card', 'paypal', 'bank_transfer'] %}

SELECT
    {% for method in payment_methods %}
    SUM(CASE WHEN payment_method = '{{ method }}' THEN amount END) as {{ method }}_total
    {{ "," if not loop.last }}
    {% endfor %}
FROM {{ ref('fct_orders') }}
```

**Macros** (`macros/generate_surrogate_key.sql`):
```sql
{% macro surrogate_key(columns) %}
    MD5(CONCAT({% for col in columns %}{{ col }}{{ ", '|', " if not loop.last }}{% endfor %}))
{% endmacro %}
```

**Use macro**:
```sql
SELECT
    {{ surrogate_key(['customer_id', 'valid_from']) }} as customer_key,
    ...
```

## Project Structure

```
transformations/dbt/
├── dbt_project.yml         # Project configuration
├── profiles.yml            # Connection profiles (Trino)
├── packages.yml            # DBT package dependencies
├── macros/                 # Reusable SQL snippets
│   └── generate_schema_name.sql
└── models/
    ├── sources.yml         # Raw table definitions
    ├── bronze/             # Staging layer (views)
    │   ├── stg_customers.sql
    │   ├── stg_orders.sql
    │   └── stg_products.sql
    ├── silver/             # Dimension tables (incremental)
    │   ├── dim_customer.sql
    │   ├── dim_product.sql
    │   └── dim_date.sql
    └── gold/               # Fact tables (incremental)
        └── fct_orders.sql
```

## Trino Profile Configuration

**profiles.yml**:
```yaml
lakehouse_analytics:
  target: dev
  outputs:
    dev:
      type: trino
      host: localhost  # Via port-forward: kubectl port-forward -n lakehouse svc/trino 8080:8080
      port: 8080
      database: lakehouse
      schema: analytics
      user: trino
      threads: 4

    prod:
      type: trino
      host: trino  # From within cluster (Dagster)
      port: 8080
      database: lakehouse
      schema: analytics
      user: trino
      threads: 8
```

## Common Commands

```bash
# Parse project (validate syntax)
dbt parse

# Compile models (generate SQL, don't run)
dbt compile

# Run all models
dbt run

# Run specific model and dependencies
dbt run --select +dim_customer

# Run specific model and downstream
dbt run --select dim_customer+

# Run modified models only
dbt run --select state:modified+

# Test all models
dbt test

# Test specific model
dbt test --select dim_customer

# Generate documentation
dbt docs generate

# Serve documentation (local web server)
dbt docs serve

# Full refresh (ignore incremental logic)
dbt run --full-refresh

# Run specific layer
dbt run --select bronze.*
dbt run --select silver.*
dbt run --select gold.*
```

## Integration with Lakehouse

### Bronze Layer (Staging Views)

**Purpose**: Light transformations on raw data

```sql
-- models/bronze/stg_customers.sql
{{ config(materialized='view') }}

SELECT
    customer_id::BIGINT as customer_id,
    email::VARCHAR as email,
    first_name::VARCHAR as first_name,
    last_name::VARCHAR as last_name,
    CAST(updated_at AS TIMESTAMP) as updated_at
FROM {{ source('raw', 'postgres_customers') }}
```

### Silver Layer (Dimension Tables)

**Purpose**: Cleaned, deduplicated dimensions with business logic

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

deduped AS (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY updated_at DESC) as rn
    FROM source
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
FROM deduped
WHERE rn = 1
```

### Gold Layer (Fact Tables)

**Purpose**: Star schema facts for analytics

```sql
-- models/gold/fct_orders.sql
{{
  config(
    materialized='incremental',
    unique_key='order_key',
    file_format='iceberg'
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
    o.order_date
FROM {{ ref('stg_orders') }} o
LEFT JOIN {{ ref('dim_customer') }} c ON o.customer_id = c.customer_id AND c.is_current = TRUE
LEFT JOIN {{ ref('dim_product') }} p ON o.product_id = p.product_id AND p.is_current = TRUE
LEFT JOIN {{ ref('dim_date') }} d ON DATE(o.order_date) = d.date

{% if is_incremental() %}
WHERE o.order_date > (SELECT MAX(order_date) FROM {{ this }})
{% endif %}
```

## Best Practices

### 1. Follow Naming Conventions

- **Staging**: `stg_<source>_<table>`
- **Dimensions**: `dim_<entity>`
- **Facts**: `fct_<entity>`
- **Intermediate**: `int_<entity>_<description>`

### 2. Add Descriptions

```yaml
models:
  - name: dim_customer
    description: |
      Customer dimension with SCD Type 2.
      Tracks historical changes to customer attributes.
    columns:
      - name: customer_key
        description: Surrogate key (MD5 hash)
```

### 3. Use Incremental for Large Tables

```sql
-- For tables > 1M rows
{{ config(materialized='incremental') }}
```

### 4. Test Critical Columns

```yaml
columns:
  - name: customer_key
    tests:
      - unique
      - not_null
```

### 5. Use Ref() for Dependencies

Never hardcode table names - always use `{{ ref() }}` for DBT dependency tracking.

## Integration with Other Components

- **[Trino](trino.md)**: DBT executes SQL via Trino
- **[Dagster](dagster.md)**: Orchestrates DBT runs
- **[Apache Iceberg](apache-iceberg.md)**: DBT creates Iceberg tables
- **[Medallion Architecture](medallion-architecture.md)**: DBT implements Bronze/Silver/Gold layers
- **[Star Schema](star-schema.md)**: DBT creates dimensional models

## References

- [Official DBT Documentation](https://docs.getdbt.com/)
- [DBT Best Practices](https://docs.getdbt.com/guides/best-practices)
- [DBT Trino Adapter](https://github.com/starburstdata/dbt-trino)
- [DBT Style Guide](https://github.com/dbt-labs/corp/blob/master/dbt_style_guide.md)
- Project Setup Guide: [SETUP_GUIDE.md](../../SETUP_GUIDE.md)
