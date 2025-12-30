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
from .sources.feature_export import customer_features_parquet, merchant_features_parquet
from .ml.training import fraud_detection_model, churn_prediction_model
from .ml.data_quality import validate_customer_features, validate_merchant_features


# =============================================================================
# Jobs
# =============================================================================

# Job for Payment PostgreSQL to Iceberg ingestion
# Note: Only includes payment_events, excludes quarantine (runs separately when needed)
# Concurrency key ensures only one payment pipeline job runs at a time
payment_ingestion_job = define_asset_job(
    name="payment_ingestion_job",
    selection=AssetSelection.assets(payment_events),
    description="Ingest payment events from PostgreSQL bronze layer to Iceberg",
    tags={"dagster/concurrency_key": "payment_pipeline"},
)

# =============================================================================
# Assets
# =============================================================================

all_assets = [
    # Payment ingestion assets (PostgreSQL -> Iceberg)
    payment_events,
    payment_events_quarantine,
    # Feature export assets (DBT -> MinIO Parquet -> Feast)
    customer_features_parquet,
    merchant_features_parquet,
    # ML data quality assets
    validate_customer_features,
    validate_merchant_features,
    # ML training assets (Feast + MLflow)
    fraud_detection_model,
    churn_prediction_model,
]

# =============================================================================
# Resources
# =============================================================================

all_resources = {
    # Iceberg IO Manager for persisting PyArrow Tables to Iceberg tables
    # Uses PyArrow backend for explicit schema control and Iceberg v2 compatibility
    "iceberg_io_manager": create_iceberg_io_manager(
        namespace="data",
        backend="pyarrow"
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

# Job for feature export (DBT -> MinIO Parquet for Feast)
feature_export_job = define_asset_job(
    name="feature_export_job",
    selection=AssetSelection.assets(customer_features_parquet, merchant_features_parquet),
    description="Export DBT features to MinIO parquet for Feast feature store",
)
all_jobs.append(feature_export_job)

# Job for ML model training (Feast + MLflow)
ml_training_job = define_asset_job(
    name="ml_training_job",
    selection=AssetSelection.assets(
        validate_customer_features,
        validate_merchant_features,
        fraud_detection_model,
        churn_prediction_model
    ),
    description="Train ML models using Feast features and log to MLflow. Uses champion/challenger pattern - only promotes to Production if F1 score improves.",
)
all_jobs.append(ml_training_job)

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
    # Hourly ML model training with champion/challenger
    # Models are only promoted to Production if they beat the current champion's F1 score
    ScheduleDefinition(
        job=ml_training_job,
        cron_schedule="0 * * * *",  # Every hour at minute 0
        default_status=DefaultScheduleStatus.RUNNING,  # Enabled for dev
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
    # Note: Excludes quarantine asset as it's optional and only processes failed events
    # Concurrency key ensures only one payment pipeline job runs at a time
    payment_pipeline_job = define_asset_job(
        name="payment_pipeline_job",
        selection=AssetSelection.assets(payment_events) | AssetSelection.assets(dbt_payment_assets),
        description="Full payment pipeline: PostgreSQL ingestion + DBT transformations",
        tags={"dagster/concurrency_key": "payment_pipeline"},
    )
    all_jobs.append(payment_pipeline_job)

    # Add DBT-only schedule (for manual DBT runs)
    all_schedules.append(
        ScheduleDefinition(
            job=dbt_transformation_job,
            cron_schedule="0 * * * *",  # Every hour at minute 0
            default_status=DefaultScheduleStatus.STOPPED,  # Enable when ready
        )
    )

    # Add full pipeline schedule (ingestion + DBT together)
    # This is the primary schedule for automated pipeline execution
    all_schedules.append(
        ScheduleDefinition(
            job=payment_pipeline_job,
            cron_schedule="*/15 * * * *",  # Every 15 minutes
            default_status=DefaultScheduleStatus.RUNNING,  # Enabled by default
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
