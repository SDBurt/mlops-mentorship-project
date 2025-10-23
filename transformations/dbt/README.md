# DBT Transformations

SQL-based data transformations using DBT (Data Build Tool) for the lakehouse analytics layer.

## Project Structure

```
dbt/
├── dbt_project.yml    # Project config
├── profiles.yml       # Database connections
└── models/
    ├── sources.yml    # Raw data source definitions
    ├── bronze/        # Staging layer (views from raw data)
    ├── silver/        # Dimension tables (cleaned, enriched)
    └── gold/          # Fact tables (star schema for analytics)
```

## Model Layers (Medallion Architecture)

**Bronze** - Staging views with basic cleaning
- Source: Raw Iceberg tables from Airbyte
- Materialization: Views
- Examples: `stg_customers`, `stg_orders`, `stg_products`

**Silver** - Dimension tables with business logic
- Source: Bronze staging models
- Materialization: Incremental Iceberg tables
- Examples: `dim_customer`, `dim_product`, `dim_date`

**Gold** - Fact tables for analytics (star schema)
- Source: Bronze + Silver models
- Materialization: Incremental Iceberg tables
- Examples: `fct_orders`

## Current Status

All models are **example templates** showing patterns and structure.

**Do not run** until:
1. Airbyte data sources are configured
2. Raw tables exist in `lakehouse.bronze` schema
3. `sources.yml` is updated with actual table names

## Quick Start

```bash
# Install DBT with Trino adapter
pip install dbt-trino

# Test configuration
dbt parse

# Compile SQL (generates SQL from templates)
dbt compile

# Run models (when data sources are ready)
dbt run --select bronze.*   # Run Bronze layer
dbt run --select silver.*   # Run Silver layer
dbt run --select gold.*     # Run Gold layer

# Run specific model
dbt run --select stg_customers

# Generate documentation
dbt docs generate
dbt docs serve
```

## Database Connection

DBT connects to Trino which queries Iceberg tables in Garage S3 storage.

**Local development:**
```bash
# Port-forward Trino service
kubectl port-forward svc/trino 8080:8080 -n trino

# DBT will connect to localhost:8080 (see profiles.yml)
```

**Configuration:** See `profiles.yml` for connection details

## Next Steps

1. Deploy Trino to query Iceberg tables
2. Configure Airbyte data sources
3. Ingest data to create raw tables
4. Update `sources.yml` with table names
5. Run `dbt run` to build dimensions and facts

See main [transformations README](../README.md) for more details.
