"""
DBT Integration Resource for Dagster

Provides dagster-dbt integration for orchestrating DBT models as Dagster assets.
DBT models run transformations on Iceberg tables via Trino.

Usage:
    The dbt_payment_assets function creates Dagster assets from DBT models.
    These assets automatically depend on upstream Dagster assets (like payment_events).
"""

from pathlib import Path
from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets, DbtProject
import os

# Path to the DBT project directory
# This resolves to: orchestration-dbt/dbt/ from orchestration-dagster/src/orchestration_dagster/resources/
DBT_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "orchestration-dbt" / "dbt"

# Export the project directory path for DbtCliResource
dbt_project = DBT_PROJECT_DIR

# Initialize DbtProject for manifest generation
_dbt_project_instance = DbtProject(
    project_dir=DBT_PROJECT_DIR,
)

# Prepare the manifest (generates if needed)
# This creates target/manifest.json which is needed for dbt_assets
_dbt_project_instance.prepare_if_dev()


@dbt_assets(
    manifest=_dbt_project_instance.manifest_path,
    project=_dbt_project_instance,
    select="tag:payments",  # Only include payment-tagged models
)
def dbt_payment_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    """
    Dagster assets generated from DBT payment models.

    This function:
    1. Loads DBT models tagged with 'payments' from the manifest
    2. Creates corresponding Dagster assets with proper dependencies
    3. Runs 'dbt build' when assets are materialized

    The dagster-dbt integration automatically:
    - Maps DBT model dependencies to Dagster asset dependencies
    - Handles DBT test execution as part of asset materialization
    - Provides DBT logs and metadata in the Dagster UI

    Tags:
        - payments: All payment-related DBT models
        - staging: Staging layer models (stg_*)
        - intermediate: Intermediate layer models (int_*)
        - marts: Mart layer models (dim_*, fct_*)
    """
    yield from dbt.cli(["build"], context=context).stream()
