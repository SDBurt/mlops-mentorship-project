"""Postgres persistence activities for payment events."""

import json
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row
from temporalio import activity

from ..config import settings


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse ISO 8601 timestamp string to datetime."""
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


@activity.defn
async def persist_to_postgres(event_data: dict[str, Any]) -> dict[str, Any]:
    """
    Persist enriched payment event to Postgres bronze table.

    Args:
        event_data: Enriched payment event data (with fraud score, validation status)

    Returns:
        Persistence result with success status
    """
    event_id = event_data.get("event_id", "unknown")
    activity.logger.info(f"Persisting to Postgres: {event_id}")

    try:
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
            "retry_strategy": json.dumps(event_data.get("retry_strategy")) if event_data.get("retry_strategy") else None,
            "retry_delay_seconds": event_data.get("retry_delay_seconds"),
            "churn_score": event_data.get("churn_score"),
            "churn_risk_level": event_data.get("churn_risk_level"),
            "days_to_churn_estimate": event_data.get("days_to_churn_estimate"),
            "validation_status": event_data.get("validation_status", "passed"),
            "validation_errors": json.dumps(event_data.get("validation_errors", [])),
            "provider_created_at": provider_created_at,
            "processed_at": processed_at,
            "ingested_at": ingested_at,
            "metadata": json.dumps(event_data.get("metadata", {})),
            "schema_version": event_data.get("schema_version", 1),
        }

        # Insert into Postgres using psycopg3 async API
        async with await psycopg.AsyncConnection.connect(settings.postgres_dsn) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO payment_events (
                        event_id, provider, provider_event_id, event_type,
                        merchant_id, customer_id, amount_cents, currency,
                        payment_method_type, card_brand, card_last_four,
                        status, failure_code, failure_message,
                        fraud_score, risk_level, retry_strategy, retry_delay_seconds,
                        churn_score, churn_risk_level, days_to_churn_estimate,
                        validation_status, validation_errors,
                        provider_created_at, processed_at, ingested_at,
                        metadata, schema_version
                    ) VALUES (
                        %(event_id)s, %(provider)s, %(provider_event_id)s, %(event_type)s,
                        %(merchant_id)s, %(customer_id)s, %(amount_cents)s, %(currency)s,
                        %(payment_method_type)s, %(card_brand)s, %(card_last_four)s,
                        %(status)s, %(failure_code)s, %(failure_message)s,
                        %(fraud_score)s, %(risk_level)s, %(retry_strategy)s, %(retry_delay_seconds)s,
                        %(churn_score)s, %(churn_risk_level)s, %(days_to_churn_estimate)s,
                        %(validation_status)s, %(validation_errors)s,
                        %(provider_created_at)s, %(processed_at)s, %(ingested_at)s,
                        %(metadata)s, %(schema_version)s
                    )
                    ON CONFLICT (event_id) DO UPDATE SET
                        fraud_score = EXCLUDED.fraud_score,
                        risk_level = EXCLUDED.risk_level,
                        retry_strategy = EXCLUDED.retry_strategy,
                        retry_delay_seconds = EXCLUDED.retry_delay_seconds,
                        churn_score = EXCLUDED.churn_score,
                        churn_risk_level = EXCLUDED.churn_risk_level,
                        days_to_churn_estimate = EXCLUDED.days_to_churn_estimate,
                        validation_status = EXCLUDED.validation_status,
                        validation_errors = EXCLUDED.validation_errors,
                        processed_at = EXCLUDED.processed_at,
                        ingested_at = EXCLUDED.ingested_at,
                        metadata = EXCLUDED.metadata
                    """,
                    record,
                )
                await conn.commit()

        activity.heartbeat()
        activity.logger.info(f"Successfully persisted {event_id} to payment_events")

        return {
            "success": True,
            "table": "payment_events",
            "event_id": event_id,
            "ingested_at": ingested_at.isoformat(),
        }

    except Exception as e:
        activity.logger.error(f"Failed to persist {event_id} to Postgres: {e}")
        return {
            "success": False,
            "event_id": event_id,
            "error": str(e),
        }


@activity.defn
async def persist_quarantine_to_postgres(dlq_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Persist DLQ event to quarantine table in Postgres.

    Args:
        dlq_payload: DLQ payload with original event and error details

    Returns:
        Persistence result with success status
    """
    event_id = dlq_payload.get("event_id", "unknown")
    activity.logger.info(f"Persisting to quarantine: {event_id}")

    try:
        record = {
            "event_id": dlq_payload.get("event_id"),
            "provider": dlq_payload.get("provider"),
            "provider_event_id": dlq_payload.get("provider_event_id"),
            "original_payload": json.dumps(dlq_payload.get("original_payload", {})),
            "validation_errors": json.dumps(dlq_payload.get("validation_errors", [])),
            "failure_reason": dlq_payload.get("failure_reason"),
            "source_topic": dlq_payload.get("source_topic"),
            "kafka_partition": dlq_payload.get("kafka_partition"),
            "kafka_offset": dlq_payload.get("kafka_offset"),
            "schema_version": dlq_payload.get("schema_version", 1),
        }

        async with await psycopg.AsyncConnection.connect(settings.postgres_dsn) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO payment_events_quarantine (
                        event_id, provider, provider_event_id,
                        original_payload, validation_errors, failure_reason,
                        source_topic, kafka_partition, kafka_offset,
                        schema_version, updated_at
                    ) VALUES (
                        %(event_id)s, %(provider)s, %(provider_event_id)s,
                        %(original_payload)s, %(validation_errors)s, %(failure_reason)s,
                        %(source_topic)s, %(kafka_partition)s, %(kafka_offset)s,
                        %(schema_version)s, NOW()
                    )
                    ON CONFLICT (event_id) DO UPDATE SET
                        original_payload = EXCLUDED.original_payload,
                        validation_errors = EXCLUDED.validation_errors,
                        failure_reason = EXCLUDED.failure_reason,
                        source_topic = EXCLUDED.source_topic,
                        kafka_partition = EXCLUDED.kafka_partition,
                        kafka_offset = EXCLUDED.kafka_offset,
                        schema_version = EXCLUDED.schema_version,
                        updated_at = NOW()
                    """,
                    record,
                )
                await conn.commit()

        activity.heartbeat()
        activity.logger.info(f"Successfully quarantined {event_id}")

        return {
            "success": True,
            "table": "payment_events_quarantine",
            "event_id": event_id,
        }

    except Exception as e:
        activity.logger.error(f"Failed to quarantine {event_id}: {e}")
        return {
            "success": False,
            "event_id": event_id,
            "error": str(e),
        }
