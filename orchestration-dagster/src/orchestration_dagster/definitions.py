"""
Dagster Definitions for Payment Pipeline

Central configuration for all Dagster assets, resources, and jobs.
Orchestrates payment event ingestion from PostgreSQL to Iceberg,
DBT transformations, and data quality monitoring.
"""

from dagster import (
    Definitions,
    AssetSelection,
    define_asset_job,
    ScheduleDefinition,
    DefaultScheduleStatus,
)

from .resources.iceberg import create_iceberg_io_manager
from .resources.postgres import PostgresResource
from .resources.dbt import dbt_payment_assets, dbt_project

from .sources.payment_ingestion import payment_events, payment_events_quarantine


# =============================================================================
# Jobs
# =============================================================================

# Job for Payment PostgreSQL to Iceberg ingestion
payment_ingestion_job = define_asset_job(
    name="payment_ingestion_job",
    selection=AssetSelection.groups("payment_ingestion"),
    description="Ingest payment events from PostgreSQL bronze layer to Iceberg",
)

# =============================================================================
# Assets
# =============================================================================

all_assets = [
    # Payment ingestion assets (PostgreSQL -> Iceberg)
    payment_events,
    payment_events_quarantine,
]

# =============================================================================
# Resources
# =============================================================================

all_resources = {
    # Iceberg IO Manager for persisting DataFrames to Iceberg tables
    "iceberg_io_manager": create_iceberg_io_manager(
        namespace="data",
        backend="pandas"
    ),

    # PostgreSQL resource for reading payment events from bronze layer
    # Host is configured via PAYMENTS_DB_HOST environment variable
    # Defaults: "localhost" for local development, "payments-db" in Docker
    "postgres_resource": PostgresResource(),
}

# =============================================================================
# Jobs List
# =============================================================================

all_jobs = [
    payment_ingestion_job,
]

# =============================================================================
# Schedules
# =============================================================================

all_schedules = [
    # Run payment ingestion every 15 minutes
    ScheduleDefinition(
        job=payment_ingestion_job,
        cron_schedule="*/15 * * * *",  # Every 15 minutes
        default_status=DefaultScheduleStatus.STOPPED,  # Enable when ready
    ),
]

# =============================================================================
# DBT Integration (Optional)
# =============================================================================

if dbt_payment_assets is not None and dbt_project is not None:
    from dagster_dbt import DbtCliResource

    # Add DBT assets
    all_assets.append(dbt_payment_assets)

    # Add DBT resource
    all_resources["dbt"] = DbtCliResource(project_dir=dbt_project)

    # Add DBT jobs
    dbt_transformation_job = define_asset_job(
        name="dbt_transformation_job",
        selection=AssetSelection.assets(dbt_payment_assets),
        description="Run DBT transformations on payment Iceberg tables",
    )
    all_jobs.append(dbt_transformation_job)

    # Add full pipeline job (ingestion + DBT)
    payment_pipeline_job = define_asset_job(
        name="payment_pipeline_job",
        selection=AssetSelection.groups("payment_ingestion") | AssetSelection.assets(dbt_payment_assets),
        description="Full payment pipeline: PostgreSQL ingestion + DBT transformations",
    )
    all_jobs.append(payment_pipeline_job)

    # Add DBT schedule
    all_schedules.append(
        ScheduleDefinition(
            job=dbt_transformation_job,
            cron_schedule="0 * * * *",  # Every hour at minute 0
            default_status=DefaultScheduleStatus.STOPPED,  # Enable when ready
        )
    )


# =============================================================================
# Definitions
# =============================================================================

defs = Definitions(
    assets=all_assets,
    resources=all_resources,
    jobs=all_jobs,
    schedules=all_schedules,
)
