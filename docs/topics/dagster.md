# Dagster - Data Orchestration Platform

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established Dagster concepts and this project's architecture, please verify critical details against official Dagster documentation and your specific use cases.

## Overview

Dagster is a modern data orchestration platform designed for building, testing, and monitoring data pipelines. Unlike traditional workflow tools (Airflow), Dagster is asset-centric: it focuses on the data assets you're producing (tables, models, ML models) rather than just tasks.

In this lakehouse platform, Dagster orchestrates [DBT](dbt.md) transformations, schedules data refreshes, tracks lineage from [Airbyte](airbyte.md) ingestion through [Trino](trino.md) queries, and monitors data quality across the [Medallion Architecture](medallion-architecture.md).

## Why Dagster for This Platform?

**Asset-Centric**: Define data assets (tables, models) and their dependencies - Dagster handles execution order automatically.

**DBT Integration**: Native DBT support - Dagster imports DBT models as assets with lineage.

**Data Observability**: Track data quality, freshness, and lineage across entire pipeline.

**Development Experience**: Local development, unit testing, and rich UI for debugging.

**Declarative Pipelines**: Define what to produce, not how to schedule tasks.

## Key Concepts

### 1. Assets

**What it is**: A data asset is a persistent object (table, file, ML model) produced by computation.

**Example assets in this platform**:
- `bronze.stg_customers` - Staging view over raw data
- `silver.dim_customer` - Cleaned dimension table
- `gold.fct_orders` - Fact table for analytics
- `metrics.daily_revenue` - Aggregated metrics

**Asset definition**:
```python
from dagster import asset

@asset
def stg_customers(context):
    """Raw customers staging table"""
    context.log.info("Materializing stg_customers")
    # Execute DBT model
    dbt_cli_resource.run(select="stg_customers")
    return "stg_customers materialized"
```

**Asset dependencies**:
```python
@asset
def dim_customer(context, stg_customers):
    """Depends on stg_customers"""
    dbt_cli_resource.run(select="dim_customer")
    return "dim_customer materialized"

@asset
def fct_orders(context, dim_customer):
    """Depends on dim_customer"""
    dbt_cli_resource.run(select="fct_orders")
    return "fct_orders materialized"
```

**Dagster automatically determines execution order**: `stg_customers` → `dim_customer` → `fct_orders`

### 2. Asset Materialization

**What it is**: The act of computing and persisting an asset.

**Triggers**:
- **Manual**: Click "Materialize" in UI
- **Schedule**: Run daily at 2 AM
- **Sensor**: React to new data arrival
- **Asset sensor**: Materialize when upstream asset updates

**Example schedule**:
```python
from dagster import ScheduleDefinition

daily_refresh = ScheduleDefinition(
    job=define_asset_job("daily_refresh", selection="*"),
    cron_schedule="0 2 * * *",  # 2 AM daily
)
```

**Materialization result**:
- Asset marked as "Materialized" with timestamp
- Metadata logged (row count, runtime, errors)
- Lineage tracked (which upstream assets triggered this)

### 3. Jobs

**What it is**: A selection of assets to materialize together.

**Example jobs**:
```python
from dagster import define_asset_job, AssetSelection

# Job: Materialize all bronze layer assets
bronze_job = define_asset_job(
    name="bronze_refresh",
    selection=AssetSelection.groups("bronze")
)

# Job: Materialize entire pipeline
full_refresh = define_asset_job(
    name="full_refresh",
    selection="*"  # All assets
)

# Job: Materialize specific asset and downstream
customer_pipeline = define_asset_job(
    name="customer_pipeline",
    selection=AssetSelection.keys("stg_customers").downstream()
)
```

### 4. Sensors

**What it is**: Monitors external events and triggers jobs when conditions are met.

**Use cases**:
- **File sensor**: Trigger when new file appears in S3
- **Asset sensor**: Trigger when upstream asset materializes
- **Airbyte sensor**: Trigger when Airbyte sync completes

**Example - Airbyte sensor**:
```python
from dagster import sensor, RunRequest

@sensor(job=bronze_job)
def airbyte_sync_sensor(context):
    """Trigger bronze refresh when Airbyte sync completes"""
    # Check Airbyte API for completed syncs
    last_sync = check_airbyte_sync_status()

    if last_sync.status == "succeeded":
        yield RunRequest(
            run_key=f"airbyte_{last_sync.sync_id}",
            tags={"source": "airbyte", "sync_id": last_sync.sync_id}
        )
```

### 5. Resources

**What it is**: External services that assets depend on (databases, APIs, file systems).

**Example resources**:
```python
from dagster import resource
from dagster_dbt import DbtCliResource
from dagster_trino import TrinoResource

@resource
def dbt_resource(context):
    return DbtCliResource(
        project_dir="/opt/dagster/app/dbt",
        profiles_dir="/opt/dagster/app/dbt",
        target="prod"
    )

@resource
def trino_resource(context):
    return TrinoResource(
        host="trino.trino.svc.cluster.local",
        port=8080,
        catalog="lakehouse",
        schema="analytics"
    )
```

**Using resources in assets**:
```python
@asset(required_resource_keys={"dbt", "trino"})
def dim_customer(context):
    dbt = context.resources.dbt
    dbt.run(select="dim_customer")

    trino = context.resources.trino
    result = trino.execute("SELECT COUNT(*) FROM dim_customer")
    context.log.info(f"dim_customer has {result} rows")
```

### 6. Code Locations

**What it is**: Python packages/modules containing Dagster definitions (assets, jobs, schedules).

**In this platform**:
```
orchestration/dagster/
├── dagster_workspace.yaml      # Workspace config
├── lakehouse_analytics/        # Code location
│   ├── __init__.py
│   ├── assets/
│   │   ├── bronze.py          # Bronze layer assets
│   │   ├── silver.py          # Silver layer assets
│   │   └── gold.py            # Gold layer assets
│   ├── jobs.py                # Job definitions
│   ├── schedules.py           # Schedules
│   └── sensors.py             # Sensors
└── pyproject.toml             # Dependencies
```

**Load code location**:
```yaml
# dagster_workspace.yaml
load_from:
  - python_package:
      package_name: lakehouse_analytics
      location_name: lakehouse_analytics
```

## Deployment in Kubernetes

### Architecture

Dagster deployed as multiple components:

**Core Components**:
- **dagster-webserver**: UI and GraphQL API (port 80)
- **dagster-daemon**: Background services (schedules, sensors, run launcher)
- **dagster-postgresql**: Metadata storage (run history, asset catalog)
- **dagster-user-deployments**: User code servers (your assets/jobs)

**Deployment command**:
```bash
helm upgrade --install dagster dagster/dagster \
  -f infrastructure/kubernetes/dagster/values.yaml \
  -n dagster --create-namespace
```

**Key configuration** (`values.yaml`):
```yaml
dagsterWebserver:
  replicaCount: 1
  service:
    type: ClusterIP
    port: 80

dagsterDaemon:
  replicaCount: 1

postgresql:
  enabled: true
  postgresqlUsername: dagster
  postgresqlPassword: <secret>
  postgresqlDatabase: dagster

# User code deployments
dagster-user-deployments:
  enabled: true
  deployments:
    - name: lakehouse-analytics
      image:
        repository: my-registry/lakehouse-analytics
        tag: latest
      dagsterApiGrpcArgs:
        - "--python-file"
        - "/opt/dagster/app/repository.py"
```

### Accessing Dagster UI

**Port-forward**:
```bash
kubectl port-forward -n dagster svc/dagster-dagster-webserver 3000:80
```

**Access**: http://localhost:3000

## DBT Integration

### Native DBT Support

Dagster treats DBT models as assets automatically:

**Install dagster-dbt**:
```bash
pip install dagster-dbt
```

**Load DBT project**:
```python
from dagster_dbt import load_assets_from_dbt_project

dbt_assets = load_assets_from_dbt_project(
    project_dir="/path/to/dbt",
    profiles_dir="/path/to/dbt",
    target="prod"
)
```

**Result**: All DBT models appear as Dagster assets with:
- Lineage from DBT `ref()` and `source()`
- Asset groups by DBT schema (bronze, silver, gold)
- Metadata from DBT (descriptions, tests, tags)

### DBT Asset Example

**DBT model** (`models/silver/dim_customer.sql`):
```sql
{{
  config(
    materialized='incremental',
    unique_key='customer_key'
  )
}}

SELECT
    customer_key,
    customer_id,
    email,
    first_name,
    last_name
FROM {{ ref('stg_customers') }}
```

**Dagster asset** (auto-generated):
```python
# Asset: silver.dim_customer
# Upstream: bronze.stg_customers
# Group: silver
# Materialization: Executes DBT model
```

**Lineage in UI**:
```
bronze.stg_customers
    ↓
silver.dim_customer
    ↓
gold.fct_orders
```

## Common Operations

### Materialize Asset

**Via UI**:
1. Assets → Select asset (e.g., `dim_customer`)
2. Click "Materialize"
3. Monitor progress in "Runs" tab

**Via API**:
```python
from dagster import execute_job

result = execute_job(
    job=customer_pipeline,
    instance=dagster_instance
)
```

### Schedule Job

**Define schedule**:
```python
from dagster import ScheduleDefinition, define_asset_job

daily_refresh_job = define_asset_job("daily_refresh", selection="*")

daily_schedule = ScheduleDefinition(
    job=daily_refresh_job,
    cron_schedule="0 2 * * *"  # 2 AM daily
)
```

**Turn on schedule** (UI):
1. Overview → Schedules
2. Toggle "daily_schedule" to ON

### View Lineage

**Via UI**:
1. Assets → Select asset
2. Click "Lineage" tab
3. View upstream and downstream dependencies

**Example lineage**:
```
Airbyte (external) → bronze.stg_customers → silver.dim_customer → gold.fct_orders → BI Dashboard (external)
```

### Monitor Data Quality

**Add checks to assets**:
```python
from dagster import asset, AssetCheckResult

@asset
def dim_customer(context):
    # Materialize asset
    context.resources.dbt.run(select="dim_customer")

    # Data quality check
    row_count = context.resources.trino.execute(
        "SELECT COUNT(*) FROM dim_customer"
    )

    if row_count < 1000:
        return AssetCheckResult(
            passed=False,
            description=f"Expected >1000 rows, got {row_count}"
        )

    return AssetCheckResult(passed=True)
```

## Integration with Lakehouse

### Airbyte → Dagster

**Sensor triggers DBT after Airbyte sync**:
```python
@sensor(job=bronze_refresh_job)
def airbyte_sensor(context):
    # Poll Airbyte API
    syncs = check_airbyte_syncs()

    for sync in syncs:
        if sync.status == "succeeded" and sync.connection == "postgres_customers":
            yield RunRequest(
                run_key=f"airbyte_{sync.id}",
                tags={"airbyte_sync_id": sync.id}
            )
```

### Dagster → DBT → Trino

**Flow**:
1. Dagster schedules DBT job
2. DBT executes SQL against [Trino](trino.md)
3. Trino materializes [Iceberg](apache-iceberg.md) tables in [Garage](garage.md)
4. Dagster logs metadata (rows, runtime)

### Asset Metadata

**Log metadata in assets**:
```python
from dagster import AssetMaterialization, Output

@asset
def dim_customer(context):
    context.resources.dbt.run(select="dim_customer")

    # Query metadata
    stats = context.resources.trino.execute("""
        SELECT
            COUNT(*) as row_count,
            COUNT(DISTINCT customer_id) as unique_customers
        FROM dim_customer
    """)

    yield AssetMaterialization(
        asset_key="dim_customer",
        metadata={
            "row_count": stats.row_count,
            "unique_customers": stats.unique_customers,
            "freshness": "2025-01-20 10:00:00"
        }
    )
```

## Troubleshooting

### Code Location Unavailable

**Symptom**: UI shows "Code location unavailable"

**Check**:
```bash
kubectl get pods -n dagster
kubectl logs -n dagster dagster-dagster-user-deployments-<pod>
```

**Common causes**:
- Python import errors
- Missing dependencies
- Invalid Dagster definitions

### PostgreSQL Connection Failed

**Check**:
```bash
kubectl get pods -n dagster | grep postgresql
kubectl logs -n dagster dagster-postgresql-0
```

**Verify connection string** in values.yaml matches PostgreSQL service.

### Schedules Not Running

**Check daemon**:
```bash
kubectl logs -n dagster -l component=dagster-daemon
```

**Verify**:
- Daemon pod running
- Schedule turned ON in UI
- Timezone configuration correct

## Best Practices

### 1. Group Assets by Layer

```python
@asset(group_name="bronze")
def stg_customers(): ...

@asset(group_name="silver")
def dim_customer(): ...

@asset(group_name="gold")
def fct_orders(): ...
```

### 2. Add Asset Descriptions

```python
@asset(description="Customer dimension with SCD Type 2")
def dim_customer(): ...
```

### 3. Use Partitions for Historical Data

```python
from dagster import DailyPartitionsDefinition

daily_partition = DailyPartitionsDefinition(start_date="2025-01-01")

@asset(partitions_def=daily_partition)
def daily_events(context):
    partition_date = context.partition_key
    # Process only data for partition_date
```

### 4. Implement Data Quality Checks

```python
@asset
def dim_customer(context):
    # Materialize
    ...

    # Check nulls
    null_count = trino.execute("SELECT COUNT(*) FROM dim_customer WHERE email IS NULL")
    if null_count > 0:
        context.log.warning(f"{null_count} customers have NULL email")
```

### 5. Log Metadata

Log useful metrics for observability:
```python
yield AssetMaterialization(
    asset_key="dim_customer",
    metadata={
        "row_count": row_count,
        "runtime_seconds": elapsed_time,
        "data_freshness": max_updated_at
    }
)
```

## Integration with Other Components

- **[DBT](dbt.md)**: Dagster orchestrates DBT transformations
- **[Trino](trino.md)**: DBT executes SQL via Trino
- **[Airbyte](airbyte.md)**: Sensors trigger pipelines after ingestion
- **[Medallion Architecture](medallion-architecture.md)**: Asset groups map to Bronze/Silver/Gold

## References

- [Official Dagster Documentation](https://docs.dagster.io/)
- [Dagster + DBT](https://docs.dagster.io/integrations/dbt)
- [Dagster Concepts](https://docs.dagster.io/concepts)
- [Dagster Helm Chart](https://artifacthub.io/packages/helm/dagster/dagster)
- Project Setup Guide: [SETUP_GUIDE.md](../../SETUP_GUIDE.md)
