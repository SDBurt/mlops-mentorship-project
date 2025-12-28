"""Unit tests for Adyen message handler."""

import json

import pytest

from transformer.handlers.adyen import AdyenHandler, ProcessingResult


class TestAdyenHandler:
    """Tests for AdyenHandler class."""

    @pytest.fixture
    def handler(self):
        """Create an AdyenHandler instance."""
        return AdyenHandler()

    def test_process_valid_authorisation(self, handler, valid_adyen_notification_item):
        """Test processing a valid AUTHORISATION notification."""
        raw_value = json.dumps(valid_adyen_notification_item).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.adyen.notification",
            partition=0,
            offset=100,
        )

        assert result.is_valid is True
        assert result.normalized_payload is not None
        assert result.dlq_payload is None
        assert result.event_id == "adyen:7914073381342284_AUTHORISATION"

        # Verify normalized payload structure
        payload = json.loads(result.normalized_payload)
        assert payload["provider"] == "adyen"
        assert payload["event_type"] == "payment.authorized"
        assert payload["amount_cents"] == 2000
        assert payload["currency"] == "USD"

    def test_process_valid_refund(self, handler, valid_adyen_refund_item):
        """Test processing a valid REFUND notification."""
        raw_value = json.dumps(valid_adyen_refund_item).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.adyen.notification",
            partition=0,
            offset=101,
        )

        assert result.is_valid is True
        assert result.normalized_payload is not None

        payload = json.loads(result.normalized_payload)
        assert payload["event_type"] == "refund.created"
        assert payload["status"] == "refunded"

    def test_process_failed_authorisation(self, handler, valid_adyen_failed_auth):
        """Test processing a failed AUTHORISATION notification."""
        raw_value = json.dumps(valid_adyen_failed_auth).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.adyen.notification",
            partition=0,
            offset=102,
        )

        assert result.is_valid is True
        assert result.normalized_payload is not None

        payload = json.loads(result.normalized_payload)
        assert payload["status"] == "failed"
        assert payload["failure_message"] == "Refused"

    def test_process_invalid_json(self, handler):
        """Test that invalid JSON goes to DLQ."""
        raw_value = b"not valid json {"

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.adyen.notification",
            partition=0,
            offset=103,
        )

        assert result.is_valid is False
        assert result.normalized_payload is None
        assert result.dlq_payload is not None

        dlq = json.loads(result.dlq_payload)
        assert dlq["provider"] == "adyen"
        assert dlq["failure_reason"] == "INVALID_JSON"
        assert dlq["source_topic"] == "webhooks.adyen.notification"

    def test_process_missing_required_field(self, handler, valid_adyen_notification_item):
        """Test that missing required fields go to DLQ."""
        item = valid_adyen_notification_item.copy()
        del item["pspReference"]
        raw_value = json.dumps(item).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.adyen.notification",
            partition=0,
            offset=104,
        )

        assert result.is_valid is False
        assert result.dlq_payload is not None

        dlq = json.loads(result.dlq_payload)
        assert dlq["failure_reason"] == "MISSING_PSP_REFERENCE"

    def test_process_invalid_currency(self, handler, valid_adyen_notification_item):
        """Test that invalid currency goes to DLQ."""
        item = valid_adyen_notification_item.copy()
        item["amount"]["currency"] = "INVALID"
        raw_value = json.dumps(item).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.adyen.notification",
            partition=0,
            offset=105,
        )

        assert result.is_valid is False
        assert result.dlq_payload is not None

        dlq = json.loads(result.dlq_payload)
        assert "INVALID_CURRENCY" in dlq["failure_reason"]

    def test_dlq_payload_structure(self, handler):
        """Test DLQ payload has required fields."""
        raw_value = b"invalid"

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.adyen.notification",
            partition=1,
            offset=200,
        )

        assert result.dlq_payload is not None
        dlq = json.loads(result.dlq_payload)

        # Check required DLQ fields
        assert "provider" in dlq
        assert dlq["provider"] == "adyen"
        assert "original_payload" in dlq
        assert "validation_errors" in dlq
        assert "failure_reason" in dlq
        assert "source_topic" in dlq
        assert "kafka_partition" in dlq
        assert dlq["kafka_partition"] == 1
        assert "kafka_offset" in dlq
        assert dlq["kafka_offset"] == 200
        assert "quarantined_at" in dlq
        assert "schema_version" in dlq

    def test_process_unicode_in_payload(self, handler, valid_adyen_notification_item):
        """Test handling of Unicode characters in payload."""
        item = valid_adyen_notification_item.copy()
        item["merchantReference"] = "order_with_unicode_"
        raw_value = json.dumps(item, ensure_ascii=False).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.adyen.notification",
            partition=0,
            offset=106,
        )

        assert result.is_valid is True
        assert result.normalized_payload is not None

    def test_event_id_format(self, handler, valid_adyen_notification_item):
        """Test that event ID follows expected format."""
        raw_value = json.dumps(valid_adyen_notification_item).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.adyen.notification",
            partition=0,
            offset=107,
        )

        # Event ID should be adyen:{pspReference}_{eventCode}
        assert result.event_id == "adyen:7914073381342284_AUTHORISATION"

        payload = json.loads(result.normalized_payload)
        assert payload["event_id"] == "adyen:7914073381342284_AUTHORISATION"

    def test_process_capture_event(self, handler, valid_adyen_notification_item):
        """Test processing a CAPTURE event."""
        item = valid_adyen_notification_item.copy()
        item["eventCode"] = "CAPTURE"
        item["originalReference"] = item["pspReference"]
        item["pspReference"] = "9914073381342287"
        raw_value = json.dumps(item).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.adyen.notification",
            partition=0,
            offset=108,
        )

        assert result.is_valid is True
        payload = json.loads(result.normalized_payload)
        assert payload["event_type"] == "payment.captured"
        assert payload["status"] == "captured"

    def test_process_chargeback_event(self, handler, valid_adyen_notification_item):
        """Test processing a CHARGEBACK event."""
        item = valid_adyen_notification_item.copy()
        item["eventCode"] = "CHARGEBACK"
        item["success"] = True
        raw_value = json.dumps(item).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.adyen.notification",
            partition=0,
            offset=109,
        )

        assert result.is_valid is True
        payload = json.loads(result.normalized_payload)
        assert payload["event_type"] == "dispute.created"
        assert payload["status"] == "disputed"
