# Data Transformations with DBT Core

This directory contains DBT (Data Build Tool) models for transforming data in the lakehouse.

## Overview

DBT enables analytics engineers to transform data using SQL SELECT statements. Models are versioned, tested, and documented, following software engineering best practices.

## Setup

### Initialize DBT Project

```bash
cd dbt/

# Initialize new DBT project
dbt init lakehouse

# Or manually create project structure
```

### Configure Connection to Trino

**profiles.yml**

```yaml
lakehouse:
  target: dev
  outputs:
    dev:
      type: trino
      method: none
      host: localhost  # or trino-coordinator for in-cluster
      port: 8080
      database: iceberg
      schema: processed
      threads: 4
      http_scheme: http

    prod:
      type: trino
      method: none
      host: trino-coordinator
      port: 8080
      database: iceberg
      schema: processed
      threads: 8
      http_scheme: http
```

### Install Dependencies

```bash
# Install dbt-trino adapter
pip install dbt-trino

# Install other dependencies
pip install -r requirements.txt
```

## Project Structure

```
dbt/
├── dbt_project.yml           # Project configuration
├── profiles.yml              # Connection profiles
├── packages.yml              # Dependencies
├── models/
│   ├── staging/              # Bronze → Silver (cleaning, deduplication)
│   │   ├── _staging.yml
│   │   ├── stg_users.sql
│   │   ├── stg_events.sql
│   │   └── stg_orders.sql
│   ├── intermediate/         # Business logic, joins
│   │   ├── _intermediate.yml
│   │   ├── int_user_sessions.sql
│   │   └── int_order_items.sql
│   └── marts/                # Silver → Gold (aggregates, dimensions)
│       ├── core/
│       │   ├── _core.yml
│       │   ├── dim_users.sql
│       │   ├── dim_products.sql
│       │   └── fct_orders.sql
│       └── analytics/
│           ├── _analytics.yml
│           ├── user_metrics.sql
│           └── product_metrics.sql
├── tests/
│   ├── assert_positive_totals.sql
│   └── assert_valid_dates.sql
├── macros/
│   ├── generate_schema_name.sql
│   └── custom_tests.sql
├── analyses/
│   └── exploratory_queries.sql
├── snapshots/
│   └── users_snapshot.sql
└── seeds/
    └── country_codes.csv
```

## Model Layers

### Staging Layer (Bronze → Silver)

Clean and standardize raw data:

```sql
-- models/staging/stg_users.sql
{{ config(
    materialized='incremental',
    file_format='iceberg',
    unique_key='user_id',
    incremental_strategy='merge'
) }}

WITH source AS (
    SELECT * FROM {{ source('raw', 'users') }}
    {% if is_incremental() %}
    WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
    {% endif %}
),

cleaned AS (
    SELECT
        user_id,
        LOWER(TRIM(email)) AS email,
        first_name,
        last_name,
        created_at,
        updated_at
    FROM source
    WHERE user_id IS NOT NULL
)

SELECT * FROM cleaned
```

### Intermediate Layer

Apply business logic:

```sql
-- models/intermediate/int_user_sessions.sql
{{ config(materialized='table', file_format='iceberg') }}

WITH events AS (
    SELECT * FROM {{ ref('stg_events') }}
),

sessions AS (
    SELECT
        user_id,
        session_id,
        MIN(event_timestamp) AS session_start,
        MAX(event_timestamp) AS session_end,
        COUNT(*) AS event_count
    FROM events
    GROUP BY user_id, session_id
)

SELECT * FROM sessions
```

### Marts Layer (Silver → Gold)

Create business-ready tables:

```sql
-- models/marts/core/dim_users.sql
{{ config(materialized='table', file_format='iceberg') }}

WITH users AS (
    SELECT * FROM {{ ref('stg_users') }}
),

sessions AS (
    SELECT
        user_id,
        COUNT(*) AS total_sessions,
        AVG(event_count) AS avg_events_per_session
    FROM {{ ref('int_user_sessions') }}
    GROUP BY user_id
),

final AS (
    SELECT
        u.user_id,
        u.email,
        u.first_name,
        u.last_name,
        u.created_at,
        COALESCE(s.total_sessions, 0) AS total_sessions,
        COALESCE(s.avg_events_per_session, 0) AS avg_events_per_session
    FROM users u
    LEFT JOIN sessions s ON u.user_id = s.user_id
)

SELECT * FROM final
```

## Incremental Models

For large tables, use incremental materialization:

```sql
{{ config(
    materialized='incremental',
    file_format='iceberg',
    unique_key='event_id',
    incremental_strategy='merge'
) }}

SELECT * FROM {{ source('raw', 'events') }}

{% if is_incremental() %}
WHERE event_timestamp > (SELECT MAX(event_timestamp) FROM {{ this }})
{% endif %}
```

## Testing

### Schema Tests

```yaml
# models/staging/_staging.yml
version: 2

models:
  - name: stg_users
    description: Cleaned users from production database
    columns:
      - name: user_id
        description: Primary key
        tests:
          - unique
          - not_null

      - name: email
        description: User email address
        tests:
          - unique
          - not_null
          - email_format  # custom test

      - name: created_at
        tests:
          - not_null
```

### Custom Tests

```sql
-- tests/assert_positive_totals.sql
SELECT
    order_id,
    total
FROM {{ ref('fct_orders') }}
WHERE total <= 0
```

## Macros

Reusable SQL snippets:

```sql
-- macros/cents_to_dollars.sql
{% macro cents_to_dollars(column_name) %}
    ({{ column_name }} / 100.0)::decimal(10,2)
{% endmacro %}

-- Usage in model
SELECT
    order_id,
    {{ cents_to_dollars('amount_cents') }} AS amount_dollars
FROM orders
```

## Snapshots

Track slowly changing dimensions:

```sql
-- snapshots/users_snapshot.sql
{% snapshot users_snapshot %}

{{
    config(
      target_schema='snapshots',
      unique_key='user_id',
      strategy='timestamp',
      updated_at='updated_at',
    )
}}

SELECT * FROM {{ source('raw', 'users') }}

{% endsnapshot %}
```

## Commands

```bash
# Compile models
dbt compile

# Run all models
dbt run

# Run specific model
dbt run --select stg_users

# Run models downstream of stg_users
dbt run --select stg_users+

# Test all models
dbt test

# Generate documentation
dbt docs generate
dbt docs serve

# Run snapshots
dbt snapshot

# Seed reference data
dbt seed
```

## Best Practices

1. **Naming Conventions**
   - `stg_` for staging models
   - `int_` for intermediate models
   - `dim_` for dimensions
   - `fct_` for facts

2. **Materialization Strategy**
   - Staging: incremental (for large tables) or view
   - Intermediate: ephemeral or table
   - Marts: table or incremental

3. **File Format**
   - Always use `file_format='iceberg'` for Iceberg tables
   - Leverage Iceberg features (ACID, schema evolution)

4. **Documentation**
   - Document all models and columns
   - Add descriptions to schema YAML files
   - Use `dbt docs generate` regularly

5. **Testing**
   - Add tests for all primary keys
   - Test uniqueness and not-null constraints
   - Create custom tests for business logic

6. **Version Control**
   - Commit all models, tests, and docs
   - Use feature branches for development
   - Code review before merging

## Integration with Dagster

DBT models are executed by Dagster as software-defined assets:

```python
# In orchestration/data_platform/assets/transformation.py
from dagster_dbt import load_assets_from_dbt_project

dbt_assets = load_assets_from_dbt_project(
    project_dir="../dbt",
    profiles_dir="../dbt",
    key_prefix=["dbt"]
)
```

## Iceberg-Specific Configuration

```sql
{{ config(
    materialized='incremental',
    file_format='iceberg',
    table_properties={
        'format-version': '2',
        'write.parquet.compression-codec': 'snappy'
    },
    partition_by=['date(event_timestamp)'],
    incremental_strategy='merge',
    unique_key='event_id'
) }}
```

## Resources

- [DBT Documentation](https://docs.getdbt.com/)
- [DBT Best Practices](https://docs.getdbt.com/guides/best-practices)
- [dbt-trino Adapter](https://github.com/starburstdata/dbt-trino)
- [Iceberg with DBT](https://iceberg.apache.org/docs/latest/dbt/)
- [Testing in DBT](https://docs.getdbt.com/docs/build/tests)

## Status

**Phase 1**: Setup and basic structure
**Phase 2**: Full implementation with models and tests
**Phase 3**: Production-ready with CI/CD
