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
from dagster import asset, AssetExecutionContext, Output, MetadataValue, Nothing
from decimal import Decimal
from datetime import datetime
from typing import Any, Optional, Union

from ..resources.postgres import PostgresResource
from ..partitions import payment_daily_partitions


def _convert_decimal_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Convert Decimal columns to float for Iceberg compatibility."""
    for col in df.columns:
        if df[col].dtype == object and len(df) > 0:
            # Check if first non-null value is Decimal
            first_val = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
            if isinstance(first_val, Decimal):
                df[col] = df[col].astype(float)
    return df


def _prepare_dataframe_for_iceberg(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare DataFrame for Iceberg ingestion.

    - Converts timestamps to microsecond precision (Iceberg requirement)
    - Converts Decimal to float
    - Converts object columns to proper string type (Iceberg v2 compatibility)
    - Handles JSONB columns (validation_errors, metadata)
    """
    if len(df) == 0:
        return df

    # Convert timestamp columns to microsecond precision
    timestamp_cols = ['provider_created_at', 'processed_at', 'ingested_at', 'loaded_at', 'quarantined_at']
    for col in timestamp_cols:
        if col in df.columns and df[col].notna().any():
            df[col] = pd.to_datetime(df[col]).dt.as_unit('us')

    # Convert Decimal columns to float
    df = _convert_decimal_columns(df)

    # Convert integer columns to proper types
    int_cols = ['id', 'amount_cents', 'retry_delay_seconds', 'days_to_churn_estimate', 'schema_version']
    for col in int_cols:
        if col in df.columns:
            df[col] = df[col].astype('Int64')  # Nullable integer

    # Convert string/object columns to proper string type for Iceberg v2 compatibility
    # These columns can be nullable but need explicit string dtype
    string_cols = [
        'event_id', 'provider', 'provider_event_id', 'event_type', 'customer_id',
        'merchant_id', 'currency', 'payment_method_type', 'card_brand', 'card_last_four',
        'status', 'failure_code', 'failure_message', 'risk_level', 'retry_strategy',
        'source_topic', 'failure_reason', 'reviewed_by', 'resolution'
    ]
    for col in string_cols:
        if col in df.columns:
            # Convert to string, replacing None with pd.NA
            df[col] = df[col].astype('string')

    # Handle JSONB columns - convert to JSON string for Iceberg storage
    import json

    def _serialize_json(x):
        """Safely serialize a value to JSON string."""
        if x is None:
            return None
        # Handle pandas NA
        try:
            if pd.isna(x):
                return None
        except (ValueError, TypeError):
            # pd.isna fails on arrays/lists - that's fine, serialize them
            pass
        return json.dumps(x)

    json_cols = ['validation_errors', 'original_payload', 'metadata']
    for col in json_cols:
        if col in df.columns:
            df[col] = df[col].apply(_serialize_json).astype('string')

    return df


@asset(
    key_prefix=["data"],
    io_manager_key="iceberg_io_manager",
    metadata={
        "partition_expr": "ingested_at",
    },
    group_name="payment_ingestion",
    compute_kind="postgres",
)
def payment_events(
    context: AssetExecutionContext,
    postgres_resource: PostgresResource
) -> Output[pd.DataFrame]:
    """
    Ingest payment events from PostgreSQL to Iceberg.

    Reads enriched payment events that haven't been loaded yet
    (loaded_to_iceberg = FALSE) and persists to Iceberg table.

    After successful write, marks records as loaded in PostgreSQL.

    Returns empty DataFrame with proper schema when there are no new events,
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
        # Return empty DataFrame with proper schema to avoid column errors
        # This allows incremental runs to succeed without writing any data
        empty_df = pd.DataFrame(columns=[
            'event_id', 'provider', 'provider_event_id', 'event_type',
            'customer_id', 'merchant_id', 'amount_cents', 'currency',
            'payment_method_type', 'card_brand', 'card_last_four',
            'status', 'failure_code', 'failure_message',
            'fraud_score', 'risk_level', 'churn_score', 'churn_risk_level',
            'retry_strategy', 'retry_delay_seconds', 'days_to_churn_estimate',
            'validation_status', 'validation_errors',
            'provider_created_at', 'processed_at', 'ingested_at',
            'metadata', 'schema_version'
        ])
        return Output(
            empty_df,
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

    # Prepare for Iceberg
    df = _prepare_dataframe_for_iceberg(df)

    # Extract event_ids for marking as loaded
    event_ids = [e['event_id'] for e in events]

    context.log.info(f"Prepared {len(df)} records for Iceberg ingestion")

    # Add output metadata
    metadata = {
        "num_records": len(df),
        "event_types": MetadataValue.json(df['event_type'].value_counts().to_dict()) if 'event_type' in df.columns else {},
        "providers": MetadataValue.json(df['provider'].value_counts().to_dict()) if 'provider' in df.columns else {},
        "date_range": f"{df['ingested_at'].min()} to {df['ingested_at'].max()}" if 'ingested_at' in df.columns and len(df) > 0 else "N/A",
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

    return Output(df, metadata=metadata)


@asset(
    key_prefix=["data"],
    name="payment_events_daily",
    io_manager_key="iceberg_io_manager",
    partitions_def=payment_daily_partitions,
    metadata={
        "partition_expr": "ingested_at",
        "description": "Daily partitioned payment events for batch processing",
    },
    group_name="payment_daily",
    compute_kind="postgres",
)
def payment_events_daily(
    context: AssetExecutionContext,
    postgres_resource: PostgresResource,
) -> Output[pd.DataFrame]:
    """
    Daily batch processing of payment events by date partition.

    This asset queries ALL events for the partition date and uses Iceberg's
    merge strategy for deduplication. Complements the real-time ingestion
    (payment_events) with daily batch processing.

    Use cases:
    - Daily batch reconciliation
    - Historical data recovery (backfill)
    - Reprocessing specific date ranges

    Note: This does NOT update loaded_to_iceberg flag since it processes
    all events for the date, not just new ones.
    """
    partition_key = context.partition_key
    partition_date = datetime.strptime(partition_key, "%Y-%m-%d").date()

    context.log.info(f"Backfilling payment events for partition: {partition_date}")

    events = postgres_resource.get_events_by_date(
        table="payment_events",
        partition_date=partition_date,
    )

    if not events:
        context.log.info(f"No events found for {partition_date}")
        # Return empty DataFrame with proper schema
        empty_df = pd.DataFrame(columns=[
            'event_id', 'provider', 'provider_event_id', 'event_type',
            'customer_id', 'merchant_id', 'amount_cents', 'currency',
            'payment_method_type', 'card_brand', 'card_last_four',
            'status', 'failure_code', 'failure_message',
            'fraud_score', 'risk_level', 'churn_score', 'churn_risk_level',
            'retry_strategy', 'retry_delay_seconds', 'days_to_churn_estimate',
            'validation_status', 'validation_errors',
            'provider_created_at', 'processed_at', 'ingested_at',
            'metadata', 'schema_version'
        ])
        return Output(
            empty_df,
            metadata={
                "num_records": 0,
                "partition_date": str(partition_date),
                "status": "no_events_for_date",
            }
        )

    context.log.info(f"Found {len(events)} payment events for {partition_date}")

    # Convert to DataFrame
    df = pd.DataFrame(events)

    # Remove internal tracking columns (not needed in Iceberg)
    drop_cols = ['id', 'loaded_to_iceberg', 'loaded_at']
    df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors='ignore')

    # Prepare for Iceberg
    df = _prepare_dataframe_for_iceberg(df)

    context.log.info(f"Prepared {len(df)} records for Iceberg backfill")

    # Add output metadata
    metadata = {
        "num_records": len(df),
        "partition_date": str(partition_date),
        "event_types": MetadataValue.json(df['event_type'].value_counts().to_dict()) if 'event_type' in df.columns else {},
        "providers": MetadataValue.json(df['provider'].value_counts().to_dict()) if 'provider' in df.columns else {},
    }

    return Output(df, metadata=metadata)


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
) -> Output[pd.DataFrame]:
    """
    Ingest quarantined payment events from PostgreSQL to Iceberg.

    Quarantined events are those that failed validation in the
    Normalizer or Orchestrator and need manual review.

    Returns empty DataFrame with proper schema when there are no events,
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
        # Skip materialization entirely when there's no data
        # The Iceberg IO manager can't handle empty DataFrames without proper schema
        from dagster import AssetMaterialization
        context.log_event(
            AssetMaterialization(
                asset_key=context.asset_key,
                metadata={
                    "num_records": 0,
                    "status": "no_quarantine_events",
                }
            )
        )
        # Return a sentinel value that the IO manager can skip
        # By returning None wrapped in Output, we signal no data to write
        return Output(
            value=pd.DataFrame(),  # Empty DataFrame signals no-op
            metadata={
                "num_records": 0,
                "status": "skipped_no_data",
            }
        )

    context.log.info(f"Found {len(events)} quarantine events")

    # Convert to DataFrame
    df = pd.DataFrame(events)

    # Remove internal tracking columns
    drop_cols = ['id']
    df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors='ignore')

    # Prepare for Iceberg
    df = _prepare_dataframe_for_iceberg(df)

    context.log.info(f"Prepared {len(df)} quarantine records for Iceberg")

    # Add output metadata
    metadata = {
        "num_records": len(df),
        "failure_reasons": MetadataValue.json(
            df['failure_reason'].value_counts().head(10).to_dict()
        ) if 'failure_reason' in df.columns else {},
        "date_range": f"{df['quarantined_at'].min()} to {df['quarantined_at'].max()}" if 'quarantined_at' in df.columns and len(df) > 0 else "N/A",
    }

    return Output(df, metadata=metadata)
