"""Unit tests for Square event handler."""

import json

import pytest

from transformer.handlers.square import SquareHandler


class TestSquareHandler:
    """Tests for SquareHandler class."""

    @pytest.fixture
    def handler(self):
        """Create a SquareHandler instance."""
        return SquareHandler()

    def test_process_valid_payment_event(self, handler, valid_square_payment_event):
        """Test processing a valid payment event."""
        raw_value = json.dumps(valid_square_payment_event).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.square.payment",
            partition=0,
            offset=100,
        )

        assert result.is_valid is True
        assert result.normalized_payload is not None
        assert result.dlq_payload is None
        assert result.event_id == "square:evt_square_12345678"

        # Verify normalized payload structure
        normalized = json.loads(result.normalized_payload)
        assert normalized["event_id"] == "square:evt_square_12345678"
        assert normalized["provider"] == "square"
        assert normalized["amount_cents"] == 2000
        assert normalized["currency"] == "USD"

    def test_process_valid_refund_event(self, handler, valid_square_refund_event):
        """Test processing a valid refund event."""
        raw_value = json.dumps(valid_square_refund_event).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.square.refund",
            partition=0,
            offset=101,
        )

        assert result.is_valid is True
        assert result.normalized_payload is not None
        assert result.event_id == "square:evt_square_refund_123"

    def test_process_invalid_json(self, handler):
        """Test processing invalid JSON goes to DLQ."""
        raw_value = b"not valid json"

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.square.payment",
            partition=0,
            offset=100,
        )

        assert result.is_valid is False
        assert result.normalized_payload is None
        assert result.dlq_payload is not None

        dlq = json.loads(result.dlq_payload)
        assert dlq["provider"] == "square"
        assert dlq["failure_reason"] == "INVALID_JSON"
        assert dlq["source_topic"] == "webhooks.square.payment"
        assert dlq["kafka_partition"] == 0
        assert dlq["kafka_offset"] == 100

    def test_process_invalid_utf8(self, handler):
        """Test processing invalid UTF-8 goes to DLQ."""
        raw_value = b"\x80\x81\x82"  # Invalid UTF-8

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.square.payment",
            partition=0,
            offset=100,
        )

        assert result.is_valid is False
        assert result.dlq_payload is not None

    def test_process_validation_failure(self, handler, valid_square_payment_event):
        """Test processing event with validation errors goes to DLQ."""
        event = valid_square_payment_event.copy()
        event["data"]["object"]["payment"]["amount_money"]["currency"] = "INVALID"

        raw_value = json.dumps(event).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.square.payment",
            partition=0,
            offset=100,
        )

        assert result.is_valid is False
        assert result.dlq_payload is not None

        dlq = json.loads(result.dlq_payload)
        assert dlq["provider"] == "square"
        assert "INVALID_CURRENCY" in dlq["failure_reason"]

    def test_process_missing_data(self, handler):
        """Test processing event without data field goes to DLQ."""
        event = {
            "merchant_id": "MERCHANT123",
            "type": "payment.completed",
            "event_id": "evt_123",
            "created_at": "2024-01-15T12:00:00Z",
        }
        raw_value = json.dumps(event).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.square.payment",
            partition=0,
            offset=100,
        )

        assert result.is_valid is False
        assert result.dlq_payload is not None

    def test_dlq_payload_contains_original(self, handler, valid_square_payment_event):
        """Test DLQ payload contains original payload."""
        event = valid_square_payment_event.copy()
        event["data"]["object"]["payment"]["amount_money"]["amount"] = -100  # Invalid

        raw_value = json.dumps(event).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.square.payment",
            partition=1,
            offset=200,
        )

        assert result.is_valid is False
        dlq = json.loads(result.dlq_payload)

        assert "original_payload" in dlq
        assert dlq["kafka_partition"] == 1
        assert dlq["kafka_offset"] == 200
        assert dlq["schema_version"] == 1
        assert "quarantined_at" in dlq
