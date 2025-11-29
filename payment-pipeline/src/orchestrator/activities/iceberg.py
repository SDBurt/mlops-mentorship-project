"""Iceberg persistence activities."""

import json
from datetime import datetime, timezone
from typing import Any

import pyarrow as pa
from pyiceberg.catalog import load_catalog
from pyiceberg.exceptions import NoSuchTableError, TableAlreadyExistsError
from temporalio import activity
from temporalio.exceptions import ApplicationError

from ..config import settings


# Schema for payments bronze table
PAYMENTS_BRONZE_SCHEMA = pa.schema([
    ("event_id", pa.string()),
    ("provider", pa.string()),
    ("provider_event_id", pa.string()),
    ("event_type", pa.string()),
    ("merchant_id", pa.string()),
    ("customer_id", pa.string()),
    ("amount_cents", pa.int64()),
    ("currency", pa.string()),
    ("payment_method_type", pa.string()),
    ("card_brand", pa.string()),
    ("card_last_four", pa.string()),
    ("status", pa.string()),
    ("failure_code", pa.string()),
    ("failure_message", pa.string()),
    ("fraud_score", pa.float64()),
    ("risk_level", pa.string()),
    ("validation_status", pa.string()),
    ("provider_created_at", pa.timestamp("us", tz="UTC")),
    ("processed_at", pa.timestamp("us", tz="UTC")),
    ("ingested_at", pa.timestamp("us", tz="UTC")),
    ("metadata_json", pa.string()),
    ("schema_version", pa.int32()),
])

# Schema for quarantine table
QUARANTINE_SCHEMA = pa.schema([
    ("event_id", pa.string()),
    ("provider", pa.string()),
    ("provider_event_id", pa.string()),
    ("original_payload", pa.string()),
    ("validation_errors", pa.string()),
    ("failure_reason", pa.string()),
    ("source_topic", pa.string()),
    ("kafka_partition", pa.int32()),
    ("kafka_offset", pa.int64()),
    ("quarantined_at", pa.timestamp("us", tz="UTC")),
    ("schema_version", pa.int32()),
])


def _get_catalog():
    """Get PyIceberg catalog configured for Polaris."""
    catalog_config = {
        "uri": settings.iceberg_catalog_uri,
        "warehouse": settings.iceberg_warehouse,
        "type": "rest",
        "s3.endpoint": settings.s3_endpoint,
        "s3.access-key-id": settings.s3_access_key,
        "s3.secret-access-key": settings.s3_secret_key,
        "s3.path-style-access": "true",
    }

    # Add credentials if provided
    if settings.polaris_client_id and settings.polaris_client_secret:
        catalog_config["credential"] = (
            f"{settings.polaris_client_id}:{settings.polaris_client_secret}"
        )
        catalog_config["scope"] = "PRINCIPAL_ROLE:ALL"

    return load_catalog("default", **catalog_config)


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse ISO 8601 timestamp string to datetime."""
    if not value:
        return None
    try:
        # Handle various ISO 8601 formats
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


@activity.defn
async def persist_to_iceberg(event_data: dict[str, Any]) -> dict[str, Any]:
    """
    Persist enriched payment event to Iceberg Bronze layer.

    Args:
        event_data: Enriched payment event data (with fraud score, validation status)

    Returns:
        Persistence result with success status and table info
    """
    event_id = event_data.get("event_id", "unknown")
    activity.logger.info(f"Persisting to Iceberg: {event_id}")

    try:
        catalog = _get_catalog()
        table_name = f"{settings.iceberg_namespace}.payments_bronze"

        # Try to load table, create if doesn't exist
        try:
            table = catalog.load_table(table_name)
        except NoSuchTableError:
            try:
                activity.logger.info(f"Creating table: {table_name}")
                table = catalog.create_table(table_name, schema=PAYMENTS_BRONZE_SCHEMA)
            except TableAlreadyExistsError:
                # Another concurrent activity created the table
                table = catalog.load_table(table_name)

        # Parse timestamps
        provider_created_at = _parse_timestamp(event_data.get("provider_created_at"))
        processed_at = _parse_timestamp(event_data.get("processed_at"))
        ingested_at = datetime.now(timezone.utc)

        # Build record
        record = {
            "event_id": event_data.get("event_id"),
            "provider": event_data.get("provider"),
            "provider_event_id": event_data.get("provider_event_id"),
            "event_type": event_data.get("event_type"),
            "merchant_id": event_data.get("merchant_id"),
            "customer_id": event_data.get("customer_id"),
            "amount_cents": event_data.get("amount_cents"),
            "currency": event_data.get("currency"),
            "payment_method_type": event_data.get("payment_method_type"),
            "card_brand": event_data.get("card_brand"),
            "card_last_four": event_data.get("card_last_four"),
            "status": event_data.get("status"),
            "failure_code": event_data.get("failure_code"),
            "failure_message": event_data.get("failure_message"),
            "fraud_score": event_data.get("fraud_score"),
            "risk_level": event_data.get("risk_level"),
            "validation_status": event_data.get("validation_status", "passed"),
            "provider_created_at": provider_created_at,
            "processed_at": processed_at,
            "ingested_at": ingested_at,
            "metadata_json": json.dumps(event_data.get("metadata", {})),
            "schema_version": event_data.get("schema_version", 1),
        }

        # Convert to PyArrow table and append
        arrow_table = pa.Table.from_pylist([record], schema=PAYMENTS_BRONZE_SCHEMA)
        table.append(arrow_table)

        # Send heartbeat for long-running operations
        activity.heartbeat()

        activity.logger.info(f"Successfully persisted {event_id} to {table_name}")

        return {
            "success": True,
            "table": table_name,
            "event_id": event_id,
            "ingested_at": ingested_at.isoformat(),
        }

    except Exception as e:
        # Log warning but don't fail workflow - Iceberg is optional for demo
        activity.logger.warning(
            f"Iceberg persistence skipped for {event_id}: {e}. "
            "Configure Polaris catalog to enable persistence."
        )
        return {
            "success": False,
            "skipped": True,
            "event_id": event_id,
            "reason": str(e),
        }


@activity.defn
async def persist_quarantine(dlq_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Persist DLQ event to quarantine table in Iceberg.

    Args:
        dlq_payload: DLQ payload with original event and error details

    Returns:
        Persistence result with success status

    Raises:
        ApplicationError: If Iceberg write fails
    """
    event_id = dlq_payload.get("event_id", "unknown")
    activity.logger.info(f"Persisting to quarantine: {event_id}")

    try:
        catalog = _get_catalog()
        table_name = f"{settings.iceberg_namespace}.payments_quarantine"

        # Try to load table, create if doesn't exist
        try:
            table = catalog.load_table(table_name)
        except NoSuchTableError:
            try:
                activity.logger.info(f"Creating quarantine table: {table_name}")
                table = catalog.create_table(table_name, schema=QUARANTINE_SCHEMA)
            except TableAlreadyExistsError:
                # Another concurrent activity created the table
                table = catalog.load_table(table_name)

        # Build record
        record = {
            "event_id": dlq_payload.get("event_id"),
            "provider": dlq_payload.get("provider"),
            "provider_event_id": dlq_payload.get("provider_event_id"),
            "original_payload": dlq_payload.get("original_payload", ""),
            "validation_errors": json.dumps(dlq_payload.get("validation_errors", [])),
            "failure_reason": dlq_payload.get("failure_reason"),
            "source_topic": dlq_payload.get("source_topic"),
            "kafka_partition": dlq_payload.get("kafka_partition"),
            "kafka_offset": dlq_payload.get("kafka_offset"),
            "quarantined_at": datetime.now(timezone.utc),
            "schema_version": dlq_payload.get("schema_version", 1),
        }

        # Convert to PyArrow table and append
        arrow_table = pa.Table.from_pylist([record], schema=QUARANTINE_SCHEMA)
        table.append(arrow_table)

        activity.heartbeat()

        activity.logger.info(f"Successfully quarantined {event_id} to {table_name}")

        return {
            "success": True,
            "table": table_name,
            "event_id": event_id,
        }

    except Exception as e:
        # Log warning but don't fail workflow - Iceberg is optional for demo
        activity.logger.warning(
            f"Quarantine persistence skipped for {event_id}: {e}. "
            "Configure Polaris catalog to enable persistence."
        )
        return {
            "success": False,
            "skipped": True,
            "event_id": event_id,
            "reason": str(e),
        }
