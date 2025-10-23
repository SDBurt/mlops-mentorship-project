# Orchestration with Dagster

This directory contains Dagster pipelines and assets for orchestrating the data platform.

## Setup

### Initialize Dagster Project

```bash
cd orchestration/

# Initialize a new Dagster project
dagster project scaffold --name data-platform

# Or use the CLI to create specific components
dagster project from-example --name data-platform --example tutorial_dbt_dagster
```

### Project Structure

After initialization, your project should look like:

```
orchestration/
├── data_platform/
│   ├── __init__.py
│   ├── assets/
│   │   ├── __init__.py
│   │   ├── ingestion.py      # Airbyte integration assets
│   │   ├── transformation.py  # DBT assets
│   │   └── analytics.py       # Downstream analytics assets
│   ├── resources/
│   │   ├── __init__.py
│   │   ├── s3.py             # Garage S3 resource
│   │   ├── iceberg.py        # Iceberg catalog resource
│   │   └── airbyte.py        # Airbyte API resource
│   ├── sensors/
│   │   └── __init__.py
│   ├── schedules/
│   │   └── __init__.py
│   └── jobs/
│       └── __init__.py
├── data_platform_tests/
│   └── __init__.py
├── setup.py
├── pyproject.toml
└── README.md
```

## Development

### Run Dagster Locally

```bash
# Start Dagster webserver and daemon
dagster dev

# Access UI at http://localhost:3000
```

### Key Concepts

**Software-Defined Assets**

Assets represent data products (tables, files, ML models):

```python
from dagster import asset

@asset(
    group_name="raw",
    compute_kind="airbyte"
)
def raw_users():
    """Raw users table ingested from production database."""
    # Trigger Airbyte sync
    return trigger_airbyte_sync("users_connection")
```

**Resources**

Resources provide reusable connections to external systems:

```python
from dagster import resource

@resource(config_schema={"endpoint": str, "access_key": str})
def s3_resource(context):
    """Garage S3 resource for data storage."""
    return boto3.client(
        's3',
        endpoint_url=context.resource_config["endpoint"],
        aws_access_key_id=context.resource_config["access_key"],
        # ...
    )
```

**Sensors**

Sensors trigger jobs based on external events:

```python
from dagster import sensor, RunRequest

@sensor(job=ingest_data_job)
def new_data_sensor(context):
    """Trigger ingestion when new data is available."""
    if check_for_new_data():
        yield RunRequest(
            run_key=f"ingest_{datetime.now().isoformat()}",
            run_config={...}
        )
```

**Schedules**

Schedules trigger jobs on a cron-like schedule:

```python
from dagster import schedule

@schedule(
    job=daily_metrics_job,
    cron_schedule="0 6 * * *"  # Every day at 6 AM
)
def daily_metrics_schedule(context):
    """Calculate daily metrics."""
    return {}
```

## Integration Patterns

### Airbyte Integration

```python
from dagster import asset, AssetExecutionContext
from dagster_airbyte import airbyte_resource, build_airbyte_assets

airbyte_instance = airbyte_resource.configured({
    "host": "airbyte-airbyte-server-svc",
    "port": "8001",
})

# Auto-generate assets from Airbyte connections
airbyte_assets = build_airbyte_assets(
    connection_id="your-connection-id",
    destination_tables=["users", "events"],
    asset_key_prefix=["raw"]
)
```

### DBT Integration

```python
from dagster_dbt import dbt_cli_resource, load_assets_from_dbt_project

dbt_project_dir = Path(__file__).parent.parent.parent / "dbt"
dbt_assets = load_assets_from_dbt_project(
    project_dir=dbt_project_dir,
    profiles_dir=dbt_project_dir,
    key_prefix=["processed"]
)
```

### Iceberg Tables

```python
from pyiceberg.catalog import load_catalog

@asset
def user_features(context, dbt_users_silver):
    """Create feature table from silver layer."""
    catalog = load_catalog("default", **{
        "uri": "http://iceberg-rest-catalog:8181",
        "s3.endpoint": "http://garage-s3-api:3900",
    })

    # Read from Iceberg
    table = catalog.load_table("processed.users")
    df = table.scan().to_pandas()

    # Feature engineering
    features = engineer_features(df)

    # Write to new Iceberg table
    catalog.create_table(
        "ml.user_features",
        schema=features_schema,
    )
```

## Best Practices

1. **Asset Groups**: Organize assets by domain (ingestion, transformation, analytics)
2. **Partitioning**: Use time-based partitions for incremental processing
3. **Testing**: Write unit tests for asset logic
4. **Monitoring**: Use asset checks for data quality
5. **Documentation**: Add docstrings to all assets
6. **Dependencies**: Explicitly declare asset dependencies
7. **Idempotency**: Ensure assets can be safely re-run

## Deployment

### Kubernetes Deployment

Dagster is deployed via Helm chart. Configuration in `/infrastructure/kubernetes/dagster/values.yaml`.

**Access Dagster UI:**

```bash
# Via port-forward
kubectl port-forward -n dagster svc/dagster-dagster-webserver 3000:80

# Open http://localhost:3000
```

### Production Considerations

- **Run Isolation**: Configure run launcher for isolated execution
- **Secrets**: Use Kubernetes secrets for credentials
- **Resource Limits**: Set appropriate CPU/memory limits
- **Monitoring**: Integrate with Prometheus for metrics
- **Alerting**: Configure alerts for pipeline failures

## Examples

See example pipelines in `/orchestration/data_platform/assets/` (after initialization).

## Resources

- [Dagster Documentation](https://docs.dagster.io/)
- [Dagster + DBT Tutorial](https://docs.dagster.io/integrations/dbt)
- [Dagster + Airbyte](https://docs.dagster.io/integrations/airbyte)
- [Asset Definitions](https://docs.dagster.io/concepts/assets/software-defined-assets)
