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
from dagster_dbt import DbtCliResource

from .resources.iceberg import create_iceberg_io_manager
from .resources.trino import TrinoResource
from .resources.postgres import PostgresResource
from .resources.dbt import dbt_payment_assets, dbt_project

from .sources.payment_ingestion import payment_events, payment_events_quarantine
from .sources.payments import (
    quarantine_charges_monitor,
    quarantine_summary_monitor,
    validation_flag_monitor
)


# =============================================================================
# Jobs
# =============================================================================

# Job for Payment PostgreSQL to Iceberg ingestion
payment_ingestion_job = define_asset_job(
    name="payment_ingestion_job",
    selection=AssetSelection.groups("payment_ingestion"),
    description="Ingest payment events from PostgreSQL bronze layer to Iceberg",
)

# Job for DBT transformations
dbt_transformation_job = define_asset_job(
    name="dbt_transformation_job",
    selection=AssetSelection.assets(dbt_payment_assets),
    description="Run DBT transformations on payment Iceberg tables",
)

# Job for Payment Data Quality Monitoring
payment_dq_monitoring_job = define_asset_job(
    name="payment_dq_monitoring_job",
    selection=AssetSelection.groups("data_quality_payments"),
    description="Monitor payment quarantine tables and data quality metrics",
)

# Full pipeline job (ingestion + DBT)
payment_pipeline_job = define_asset_job(
    name="payment_pipeline_job",
    selection=AssetSelection.groups("payment_ingestion") | AssetSelection.assets(dbt_payment_assets),
    description="Full payment pipeline: PostgreSQL ingestion + DBT transformations",
)


# =============================================================================
# Schedules
# =============================================================================

# Run payment ingestion every 15 minutes
payment_ingestion_schedule = ScheduleDefinition(
    job=payment_ingestion_job,
    cron_schedule="*/15 * * * *",  # Every 15 minutes
    default_status=DefaultScheduleStatus.STOPPED,  # Enable when ready
)

# Run DBT transformations hourly
dbt_transformation_schedule = ScheduleDefinition(
    job=dbt_transformation_job,
    cron_schedule="0 * * * *",  # Every hour at minute 0
    default_status=DefaultScheduleStatus.STOPPED,  # Enable when ready
)

# Run data quality monitoring hourly
dq_monitoring_schedule = ScheduleDefinition(
    job=payment_dq_monitoring_job,
    cron_schedule="5 * * * *",  # Every hour at minute 5
    default_status=DefaultScheduleStatus.STOPPED,  # Enable when ready
)


# =============================================================================
# Definitions
# =============================================================================

defs = Definitions(
    assets=[
        # Payment ingestion assets (PostgreSQL -> Iceberg)
        payment_events,
        payment_events_quarantine,

        # DBT transformation assets
        dbt_payment_assets,

        # Payment data quality monitoring assets
        quarantine_charges_monitor,
        quarantine_summary_monitor,
        validation_flag_monitor,
    ],
    resources={
        # Iceberg IO Manager for persisting DataFrames to Iceberg tables
        "iceberg_io_manager": create_iceberg_io_manager(
            namespace="data",
            backend="pandas"
        ),

        # PostgreSQL resource for reading payment events from bronze layer
        # Host is configured via POSTGRES_HOST environment variable
        # Defaults: "localhost" for local development, "payments-db" in Docker
        "postgres_resource": PostgresResource(),

        # Trino resource for data quality monitoring queries
        # Host is configured via TRINO_HOST environment variable
        # Defaults: "trino" in Kubernetes, "localhost" for local development
        "trino_resource": TrinoResource(
            port=8080,
            catalog="iceberg",
            schema="data",
            user="dagster"
        ),

        # DBT CLI resource for running DBT commands
        "dbt": DbtCliResource(project_dir=dbt_project),
    },
    jobs=[
        payment_ingestion_job,
        dbt_transformation_job,
        payment_dq_monitoring_job,
        payment_pipeline_job,
    ],
    schedules=[
        payment_ingestion_schedule,
        dbt_transformation_schedule,
        dq_monitoring_schedule,
    ],
)
