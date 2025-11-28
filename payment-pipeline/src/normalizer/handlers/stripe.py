"""Handler for Stripe webhook events."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from ..transformers.stripe import StripeTransformer
from ..validators import ValidationResult

logger = logging.getLogger(__name__)


class ProcessingResult:
    """Result of processing a message."""

    def __init__(
        self,
        is_valid: bool,
        normalized_payload: bytes | None = None,
        dlq_payload: bytes | None = None,
        event_id: str | None = None,
    ):
        self.is_valid = is_valid
        self.normalized_payload = normalized_payload
        self.dlq_payload = dlq_payload
        self.event_id = event_id


class StripeHandler:
    """Handles Stripe webhook events."""

    def __init__(self):
        self.transformer = StripeTransformer()

    def process(
        self,
        raw_value: bytes,
        source_topic: str,
        partition: int,
        offset: int,
    ) -> ProcessingResult:
        """
        Process a raw Stripe webhook message.

        Args:
            raw_value: Raw message bytes from Kafka
            source_topic: Source Kafka topic
            partition: Kafka partition
            offset: Kafka offset

        Returns:
            ProcessingResult with normalized or DLQ payload
        """
        # Parse JSON
        try:
            raw_event = json.loads(raw_value.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Failed to parse message: %s", e)
            return self._create_dlq_result(
                raw_value=raw_value,
                source_topic=source_topic,
                partition=partition,
                offset=offset,
                errors=[{"field": "payload", "code": "INVALID_JSON", "message": str(e)}],
                event_id=None,
            )

        event_id = raw_event.get("id")

        # Transform to unified schema
        unified_event, validation_result = self.transformer.transform(raw_event)

        if validation_result.is_valid and unified_event:
            logger.debug("Successfully processed event: %s", event_id)
            return ProcessingResult(
                is_valid=True,
                normalized_payload=unified_event.model_dump_json().encode("utf-8"),
                event_id=unified_event.event_id,
            )
        else:
            logger.warning(
                "Validation failed for event %s: %s",
                event_id,
                validation_result.error_codes,
            )
            return self._create_dlq_result(
                raw_value=raw_value,
                source_topic=source_topic,
                partition=partition,
                offset=offset,
                errors=[e.to_dict() for e in validation_result.errors],
                event_id=event_id,
            )

    def _create_dlq_result(
        self,
        raw_value: bytes,
        source_topic: str,
        partition: int,
        offset: int,
        errors: list[dict[str, Any]],
        event_id: str | None,
    ) -> ProcessingResult:
        """Create a DLQ processing result."""
        dlq_payload = {
            "event_id": f"stripe:{event_id}" if event_id else None,
            "provider": "stripe",
            "provider_event_id": event_id,
            "original_payload": raw_value.decode("utf-8", errors="replace"),
            "validation_errors": errors,
            "failure_reason": errors[0]["code"] if errors else "UNKNOWN_ERROR",
            "source_topic": source_topic,
            "kafka_partition": partition,
            "kafka_offset": offset,
            "quarantined_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": 1,
        }

        return ProcessingResult(
            is_valid=False,
            dlq_payload=json.dumps(dlq_payload).encode("utf-8"),
            event_id=event_id,
        )
