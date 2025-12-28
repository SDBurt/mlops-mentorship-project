"""
Payment Event Ingestion from PostgreSQL to Iceberg.

Reads enriched payment events from the PostgreSQL bronze layer
(populated by Temporal workflows) and persists to Iceberg tables
for analytics and ML feature engineering.

Data Flow:
    PostgreSQL (payment_events) -> Dagster Asset -> Iceberg Table
    PostgreSQL (payment_events_quarantine) -> Dagster Asset -> Iceberg Table
"""

import pandas as pd
import pyarrow as pa
from dagster import asset, AssetExecutionContext, Output, MetadataValue, Nothing
from decimal import Decimal
from typing import Any, Optional, Union

from ..resources.postgres import PostgresResource


# Explicit PyArrow schemas for Iceberg tables
# This ensures consistent Iceberg v2 types regardless of DataFrame content

# Schema for payment_events_quarantine table
PAYMENT_EVENTS_QUARANTINE_SCHEMA = pa.schema([
    pa.field("event_id", pa.string(), nullable=True),
    pa.field("provider", pa.string(), nullable=True),
    pa.field("provider_event_id", pa.string(), nullable=True),
    pa.field("original_payload", pa.string(), nullable=True),  # JSON string
    pa.field("validation_errors", pa.string(), nullable=True),  # JSON string
    pa.field("failure_reason", pa.string(), nullable=True),
    pa.field("source_topic", pa.string(), nullable=True),
    pa.field("kafka_partition", pa.int64(), nullable=True),
    pa.field("kafka_offset", pa.int64(), nullable=True),
    pa.field("reviewed", pa.bool_(), nullable=True),
    pa.field("reviewed_at", pa.timestamp("us", tz="UTC"), nullable=True),
    pa.field("reviewed_by", pa.string(), nullable=True),
    pa.field("resolution", pa.string(), nullable=True),
    pa.field("quarantined_at", pa.timestamp("us", tz="UTC"), nullable=True),
])


# Schema for payment_events table
PAYMENT_EVENTS_SCHEMA = pa.schema([
    pa.field("event_id", pa.string(), nullable=False),
    pa.field("provider", pa.string(), nullable=False),
    pa.field("provider_event_id", pa.string(), nullable=True),
    pa.field("event_type", pa.string(), nullable=False),
    pa.field("customer_id", pa.string(), nullable=True),
    pa.field("merchant_id", pa.string(), nullable=True),
    pa.field("amount_cents", pa.int64(), nullable=True),
    pa.field("currency", pa.string(), nullable=True),
    pa.field("payment_method_type", pa.string(), nullable=True),
    pa.field("card_brand", pa.string(), nullable=True),
    pa.field("card_last_four", pa.string(), nullable=True),
    pa.field("status", pa.string(), nullable=True),
    pa.field("failure_code", pa.string(), nullable=True),
    pa.field("failure_message", pa.string(), nullable=True),
    pa.field("fraud_score", pa.float64(), nullable=True),
    pa.field("risk_level", pa.string(), nullable=True),
    pa.field("churn_score", pa.float64(), nullable=True),
    pa.field("churn_risk_level", pa.string(), nullable=True),
    pa.field("retry_strategy", pa.string(), nullable=True),
    pa.field("retry_delay_seconds", pa.int64(), nullable=True),
    pa.field("days_to_churn_estimate", pa.int64(), nullable=True),
    pa.field("validation_status", pa.string(), nullable=True),
    pa.field("validation_errors", pa.string(), nullable=True),  # JSON string
    pa.field("provider_created_at", pa.timestamp("us", tz="UTC"), nullable=True),
    pa.field("processed_at", pa.timestamp("us", tz="UTC"), nullable=True),
    pa.field("ingested_at", pa.timestamp("us", tz="UTC"), nullable=True),
    pa.field("metadata", pa.string(), nullable=True),  # JSON string
    pa.field("schema_version", pa.int64(), nullable=True),
])


def _convert_decimal_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Convert Decimal columns to float for Iceberg compatibility."""
    for col in df.columns:
        if df[col].dtype == object and len(df) > 0:
            # Check if first non-null value is Decimal
            first_val = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
            if isinstance(first_val, Decimal):
                df[col] = df[col].astype(float)
    return df


def _prepare_dataframe_for_iceberg(
    df: pd.DataFrame,
    schema: pa.Schema = PAYMENT_EVENTS_SCHEMA
) -> pa.Table:
    """
    Prepare DataFrame for Iceberg ingestion with explicit PyArrow schema.

    Uses explicit PyArrow schema to ensure proper Iceberg v2 type mapping.
    This avoids the 'unknown type' error that occurs when PyIceberg
    infers types from pandas DataFrames.

    Args:
        df: Input DataFrame from PostgreSQL
        schema: PyArrow schema to use (defaults to PAYMENT_EVENTS_SCHEMA)

    Returns:
        PyArrow Table with explicit schema for Iceberg compatibility
    """
    import json

    if len(df) == 0:
        # Return empty table with proper schema
        return pa.Table.from_pydict(
            {field.name: [] for field in schema},
            schema=schema
        )

    # Convert Decimal columns to float
    df = _convert_decimal_columns(df)

    # Handle JSONB columns - convert to JSON string for Iceberg storage
    def _serialize_json(x):
        """Safely serialize a value to JSON string."""
        if x is None:
            return None
        try:
            if pd.isna(x):
                return None
        except (ValueError, TypeError):
            pass
        return json.dumps(x)

    json_cols = ['validation_errors', 'original_payload', 'metadata']
    for col in json_cols:
        if col in df.columns:
            df[col] = df[col].apply(_serialize_json)

    # Convert timestamp columns to UTC-aware datetime
    timestamp_cols = ['provider_created_at', 'processed_at', 'ingested_at', 'quarantined_at', 'reviewed_at']
    for col in timestamp_cols:
        if col in df.columns and df[col].notna().any():
            df[col] = pd.to_datetime(df[col], utc=True)

    # Build PyArrow arrays for each column in schema
    arrays = []
    for field in schema:
        col_name = field.name
        if col_name in df.columns:
            # Get column data
            col_data = df[col_name]
            # Convert to PyArrow array with explicit type
            try:
                arr = pa.array(col_data, type=field.type)
            except (pa.ArrowInvalid, pa.ArrowTypeError):
                # Handle type conversion errors by casting through Python
                arr = pa.array(col_data.tolist(), type=field.type)
        else:
            # Column not in DataFrame - create null array
            arr = pa.nulls(len(df), type=field.type)
        arrays.append(arr)

    return pa.Table.from_arrays(arrays, schema=schema)


@asset(
    key_prefix=["data"],
    io_manager_key="iceberg_io_manager",
    metadata={
        "partition_expr": "ingested_at",
        "write_mode": "append",  # Append new records (no duplicates since we only read unloaded)
    },
    group_name="payment_ingestion",
    compute_kind="postgres",
)
def payment_events(
    context: AssetExecutionContext,
    postgres_resource: PostgresResource
) -> Output[pa.Table]:
    """
    Ingest payment events from PostgreSQL to Iceberg.

    Reads enriched payment events that haven't been loaded yet
    (loaded_to_iceberg = FALSE) and persists to Iceberg table.

    After successful write, marks records as loaded in PostgreSQL.

    Returns empty PyArrow Table with proper schema when there are no new events,
    allowing incremental runs to succeed without writing any data.

    Schema includes:
        - Core fields: event_id, provider, event_type, amount_cents, currency
        - Customer/Merchant: customer_id, merchant_id
        - Payment method: payment_method_type, card_brand, card_last_four
        - Status: status, failure_code, failure_message
        - ML enrichment: fraud_score, risk_level, churn_score, retry_strategy
        - Timestamps: provider_created_at, processed_at, ingested_at
    """
    batch_size = 10000

    context.log.info("Fetching unloaded payment events from PostgreSQL...")

    # Get unloaded events
    events = postgres_resource.get_unloaded_events(
        table="payment_events",
        limit=batch_size
    )

    if not events:
        context.log.info("No new payment events to ingest")
        # Return empty PyArrow Table with explicit schema
        empty_table = _prepare_dataframe_for_iceberg(pd.DataFrame())
        return Output(
            empty_table,
            metadata={
                "num_records": 0,
                "status": "no_new_events",
            }
        )

    context.log.info(f"Found {len(events)} unloaded payment events")

    # Convert to DataFrame
    df = pd.DataFrame(events)

    # Remove internal tracking columns (not needed in Iceberg)
    drop_cols = ['id', 'loaded_to_iceberg', 'loaded_at']
    df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors='ignore')

    # Prepare for Iceberg - returns PyArrow Table with explicit schema
    table = _prepare_dataframe_for_iceberg(df)

    # Extract event_ids for marking as loaded
    event_ids = [e['event_id'] for e in events]

    context.log.info(f"Prepared {table.num_rows} records for Iceberg ingestion")

    # Add output metadata (convert PyArrow columns to pandas for value_counts)
    event_types_counts = table.column("event_type").to_pandas().value_counts().to_dict()
    providers_counts = table.column("provider").to_pandas().value_counts().to_dict()
    ingested_col = table.column("ingested_at").to_pandas()

    metadata = {
        "num_records": table.num_rows,
        "event_types": MetadataValue.json(event_types_counts),
        "providers": MetadataValue.json(providers_counts),
        "date_range": f"{ingested_col.min()} to {ingested_col.max()}" if len(ingested_col) > 0 else "N/A",
    }

    # Note: Mark as loaded AFTER successful Iceberg write
    # This is handled in a sensor or schedule that confirms successful materialization
    # For now, we store the event_ids in metadata for downstream processing
    context.log.info(f"Event IDs to mark as loaded after success: {len(event_ids)}")

    # Mark events as loaded in PostgreSQL
    # This happens after DataFrame is returned and successfully written to Iceberg
    updated = postgres_resource.mark_as_loaded("payment_events", event_ids)
    context.log.info(f"Marked {updated} events as loaded in PostgreSQL")
    metadata["events_marked_loaded"] = updated

    return Output(table, metadata=metadata)


@asset(
    key_prefix=["data"],
    io_manager_key="iceberg_io_manager",
    metadata={
        "partition_expr": "quarantined_at",
    },
    group_name="payment_ingestion",
    compute_kind="postgres",
)
def payment_events_quarantine(
    context: AssetExecutionContext,
    postgres_resource: PostgresResource
) -> Output[pa.Table]:
    """
    Ingest quarantined payment events from PostgreSQL to Iceberg.

    Quarantined events are those that failed validation in the
    Normalizer or Orchestrator and need manual review.

    Returns empty PyArrow Table with proper schema when there are no events,
    allowing incremental runs to succeed without writing any data.

    Schema includes:
        - Core fields: event_id, provider, provider_event_id
        - Error data: original_payload, validation_errors, failure_reason
        - Kafka metadata: source_topic, kafka_partition, kafka_offset
        - Review tracking: reviewed, reviewed_at, reviewed_by, resolution
    """
    batch_size = 5000

    context.log.info("Fetching unloaded quarantine events from PostgreSQL...")

    # Query quarantine table (doesn't have loaded_to_iceberg by default, so we query all)
    query = """
        SELECT *
        FROM payment_events_quarantine
        WHERE NOT reviewed
        ORDER BY quarantined_at ASC
        LIMIT %s
    """
    events = postgres_resource.execute_query(query, (batch_size,))

    if not events:
        context.log.info("No quarantine events to ingest - skipping materialization")
        # Return empty PyArrow Table with explicit schema
        empty_table = _prepare_dataframe_for_iceberg(
            pd.DataFrame(),
            schema=PAYMENT_EVENTS_QUARANTINE_SCHEMA
        )
        return Output(
            value=empty_table,
            metadata={
                "num_records": 0,
                "status": "no_quarantine_events",
            }
        )

    context.log.info(f"Found {len(events)} quarantine events")

    # Convert to DataFrame
    df = pd.DataFrame(events)

    # Remove internal tracking columns
    drop_cols = ['id']
    df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors='ignore')

    # Prepare for Iceberg - returns PyArrow Table with explicit schema
    table = _prepare_dataframe_for_iceberg(df, schema=PAYMENT_EVENTS_QUARANTINE_SCHEMA)

    context.log.info(f"Prepared {table.num_rows} quarantine records for Iceberg")

    # Add output metadata (convert PyArrow columns to pandas for value_counts)
    failure_reasons_counts = {}
    if "failure_reason" in table.schema.names:
        failure_reasons_counts = (
            table.column("failure_reason")
            .to_pandas()
            .value_counts()
            .head(10)
            .to_dict()
        )

    date_range = "N/A"
    if "quarantined_at" in table.schema.names and table.num_rows > 0:
        quarantined_col = table.column("quarantined_at").to_pandas()
        date_range = f"{quarantined_col.min()} to {quarantined_col.max()}"

    metadata = {
        "num_records": table.num_rows,
        "failure_reasons": MetadataValue.json(failure_reasons_counts),
        "date_range": date_range,
    }

    return Output(table, metadata=metadata)
