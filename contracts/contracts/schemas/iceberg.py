"""
PyArrow schemas for Iceberg tables.

This module defines the explicit PyArrow schemas used for Iceberg v2 table
definitions. Using explicit schemas ensures consistent types regardless of
DataFrame content and prevents schema inference issues.

Used by:
- Dagster payment ingestion assets
- Any service writing to Iceberg tables
"""

import pyarrow as pa


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
