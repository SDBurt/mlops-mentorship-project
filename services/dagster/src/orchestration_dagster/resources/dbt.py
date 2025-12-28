"""
DBT Integration Resource for Dagster

Provides dagster-dbt integration for orchestrating DBT models as Dagster assets.
DBT models run transformations on Iceberg tables via Trino.

Usage:
    The dbt_payment_assets function creates Dagster assets from DBT models.
    These assets automatically depend on upstream Dagster assets (like payment_events).

Note:
    DBT integration is optional. If the DBT project directory is not found,
    the dbt_payment_assets will be None and can be skipped in definitions.
"""

from pathlib import Path
from dagster import AssetExecutionContext, AssetKey
from typing import Optional, Mapping, Any
import os
import logging

logger = logging.getLogger(__name__)

# Path to the DBT project directory
# Check multiple possible locations:
# 1. Environment variable (for Docker/production)
# 2. Relative path from source file (for local development)
# 3. Absolute path in container

DBT_PROJECT_DIR = None
dbt_project = None
dbt_payment_assets = None

# Try to find the DBT project
_possible_paths = [
    Path(os.environ.get("DBT_PROJECT_DIR", "")),  # From env var
    Path(__file__).resolve().parent.parent.parent.parent.parent / "orchestration-dbt" / "dbt",  # Local dev
    Path("/app/dbt"),  # Container mount point
    Path("/orchestration-dbt/dbt"),  # Alternative container path
]

for _path in _possible_paths:
    if _path.exists() and (_path / "dbt_project.yml").exists():
        DBT_PROJECT_DIR = _path
        break

if DBT_PROJECT_DIR is not None:
    try:
        from dagster_dbt import DbtCliResource, dbt_assets, DbtProject, DagsterDbtTranslator

        # Export the project directory path for DbtCliResource
        dbt_project = DBT_PROJECT_DIR

        # Initialize DbtProject for manifest generation
        _dbt_project_instance = DbtProject(
            project_dir=DBT_PROJECT_DIR,
        )

        # Prepare the manifest (generates if needed)
        # This creates target/manifest.json which is needed for dbt_assets
        _dbt_project_instance.prepare_if_dev()

        class PaymentDbtTranslator(DagsterDbtTranslator):
            """
            Custom translator to link DBT sources to upstream Dagster assets.

            Maps DBT source 'bronze_payments.payment_events' to the Dagster
            asset 'data/payment_events' so DBT models depend on the ingestion asset.
            """

            def get_asset_key(self, dbt_resource_props: Mapping[str, Any]) -> AssetKey:
                """Map DBT sources to upstream Dagster asset keys."""
                resource_type = dbt_resource_props.get("resource_type")

                if resource_type == "source":
                    # Map DBT sources to upstream Dagster assets
                    source_name = dbt_resource_props.get("source_name")
                    table_name = dbt_resource_props.get("name")

                    # bronze_payments.payment_events -> data/payment_events
                    if source_name == "bronze_payments" and table_name == "payment_events":
                        return AssetKey(["data", "payment_events"])

                    # bronze_payments.payment_events_quarantine -> data/payment_events_quarantine
                    if source_name == "bronze_payments" and table_name == "payment_events_quarantine":
                        return AssetKey(["data", "payment_events_quarantine"])

                # Default behavior for models
                return super().get_asset_key(dbt_resource_props)

        @dbt_assets(
            manifest=_dbt_project_instance.manifest_path,
            project=_dbt_project_instance,
            select="tag:payments tag:features",  # Include payment and feature models
            dagster_dbt_translator=PaymentDbtTranslator(),
        )
        def dbt_payment_assets(context: AssetExecutionContext, dbt: DbtCliResource):
            """
            Dagster assets generated from DBT payment models.

            This function:
            1. Loads DBT models tagged with 'payments' from the manifest
            2. Creates corresponding Dagster assets with proper dependencies
            3. Runs 'dbt run' when assets are materialized

            The dagster-dbt integration automatically:
            - Maps DBT model dependencies to Dagster asset dependencies
            - Links DBT sources to upstream Dagster assets (payment_events)
            - Provides DBT logs and metadata in the Dagster UI

            Note: Tests are skipped for performance. Run 'dbt test' manually
            or via a separate job when needed.

            Tags:
                - payments: All payment-related DBT models
                - staging: Staging layer models (stg_*)
                - intermediate: Intermediate layer models (int_*)
                - marts: Mart layer models (dim_*, fct_*)
            """
            yield from dbt.cli(["run"], context=context).stream()

        logger.info(f"DBT integration loaded from: {DBT_PROJECT_DIR}")

    except Exception as e:
        logger.warning(f"Failed to load DBT integration: {e}")
        dbt_payment_assets = None
        dbt_project = None
else:
    logger.warning(
        "DBT project not found. Checked paths: %s. "
        "Set DBT_PROJECT_DIR environment variable or mount the DBT project.",
        [str(p) for p in _possible_paths if str(p)]
    )
