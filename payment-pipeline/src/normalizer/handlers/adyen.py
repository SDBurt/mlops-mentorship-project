"""Handler for Adyen webhook events."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from ..transformers.adyen import AdyenTransformer
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


class AdyenHandler:
    """Handles Adyen webhook events."""

    def __init__(self):
        self.transformer = AdyenTransformer()

    def process(
        self,
        raw_value: bytes,
        source_topic: str,
        partition: int,
        offset: int,
    ) -> ProcessingResult:
        """
        Process a raw Adyen webhook message.

        Note: The gateway router pre-processes Adyen notifications to extract
        individual items. This receives a single item with its live flag.

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
            logger.warning("Failed to parse Adyen message: %s", e)
            return self._create_dlq_result(
                raw_value=raw_value,
                source_topic=source_topic,
                partition=partition,
                offset=offset,
                errors=[{"field": "payload", "code": "INVALID_JSON", "message": str(e)}],
                event_id=None,
            )

        # Build event ID from pspReference and eventCode
        psp_reference = raw_event.get("pspReference")
        event_code = raw_event.get("eventCode")
        event_id = f"{psp_reference}_{event_code}" if psp_reference and event_code else psp_reference

        # Transform to unified schema
        unified_event, validation_result = self.transformer.transform(raw_event)

        if validation_result.is_valid and unified_event:
            logger.debug("Successfully processed Adyen event: %s", event_id)
            return ProcessingResult(
                is_valid=True,
                normalized_payload=unified_event.model_dump_json().encode("utf-8"),
                event_id=unified_event.event_id,
            )
        else:
            logger.warning(
                "Validation failed for Adyen event %s: %s",
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
            "event_id": f"adyen:{event_id}" if event_id else None,
            "provider": "adyen",
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
