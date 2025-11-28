"""Unit tests for normalizer handlers."""

import json

import pytest

from normalizer.handlers.stripe import ProcessingResult, StripeHandler


class TestProcessingResult:
    """Tests for ProcessingResult class."""

    def test_valid_result(self):
        """Test creating a valid processing result."""
        result = ProcessingResult(
            is_valid=True,
            normalized_payload=b'{"event_id": "stripe:evt_123"}',
            event_id="evt_123",
        )
        assert result.is_valid is True
        assert result.normalized_payload is not None
        assert result.dlq_payload is None
        assert result.event_id == "evt_123"

    def test_invalid_result(self):
        """Test creating an invalid processing result."""
        result = ProcessingResult(
            is_valid=False,
            dlq_payload=b'{"error": "validation failed"}',
            event_id="evt_123",
        )
        assert result.is_valid is False
        assert result.normalized_payload is None
        assert result.dlq_payload is not None


class TestStripeHandler:
    """Tests for StripeHandler."""

    @pytest.fixture
    def handler(self):
        """Create a StripeHandler instance."""
        return StripeHandler()

    @pytest.fixture
    def valid_payment_intent_bytes(self):
        """Valid payment intent event as bytes."""
        event = {
            "id": "evt_1234567890abcdef",
            "type": "payment_intent.succeeded",
            "created": 1700000000,
            "data": {
                "object": {
                    "id": "pi_1234567890abcdef",
                    "amount": 2000,
                    "currency": "usd",
                    "status": "succeeded",
                    "customer": "cus_123",
                    "payment_method_types": ["card"],
                    "metadata": {},
                    "created": 1700000000,
                }
            },
        }
        return json.dumps(event).encode("utf-8")

    def test_process_valid_event(self, handler, valid_payment_intent_bytes):
        """Test processing a valid event returns normalized payload."""
        result = handler.process(
            raw_value=valid_payment_intent_bytes,
            source_topic="webhooks.stripe.payment_intent",
            partition=0,
            offset=100,
        )

        assert result.is_valid is True
        assert result.normalized_payload is not None
        assert result.dlq_payload is None
        assert result.event_id == "stripe:evt_1234567890abcdef"

        # Verify normalized payload is valid JSON
        normalized = json.loads(result.normalized_payload)
        assert normalized["event_id"] == "stripe:evt_1234567890abcdef"
        assert normalized["provider"] == "stripe"
        assert normalized["amount_cents"] == 2000
        assert normalized["currency"] == "USD"

    def test_process_invalid_json(self, handler):
        """Test processing invalid JSON goes to DLQ."""
        result = handler.process(
            raw_value=b"not valid json",
            source_topic="webhooks.stripe.payment_intent",
            partition=0,
            offset=100,
        )

        assert result.is_valid is False
        assert result.normalized_payload is None
        assert result.dlq_payload is not None

        # Verify DLQ payload structure
        dlq = json.loads(result.dlq_payload)
        assert dlq["provider"] == "stripe"
        assert dlq["failure_reason"] == "INVALID_JSON"
        assert "validation_errors" in dlq
        assert dlq["source_topic"] == "webhooks.stripe.payment_intent"
        assert dlq["kafka_partition"] == 0
        assert dlq["kafka_offset"] == 100

    def test_process_invalid_utf8(self, handler):
        """Test processing invalid UTF-8 goes to DLQ."""
        result = handler.process(
            raw_value=b"\x80\x81\x82",  # Invalid UTF-8
            source_topic="webhooks.stripe.payment_intent",
            partition=0,
            offset=100,
        )

        assert result.is_valid is False
        assert result.dlq_payload is not None

        dlq = json.loads(result.dlq_payload)
        assert dlq["failure_reason"] == "INVALID_JSON"

    def test_process_validation_failure(self, handler):
        """Test processing event with validation errors goes to DLQ."""
        # Event with invalid currency
        event = {
            "id": "evt_123",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_123",
                    "amount": 100,
                    "currency": "xyz",  # Invalid currency
                    "created": 1700000000,
                }
            },
        }
        result = handler.process(
            raw_value=json.dumps(event).encode("utf-8"),
            source_topic="webhooks.stripe.payment_intent",
            partition=0,
            offset=100,
        )

        assert result.is_valid is False
        assert result.dlq_payload is not None

        dlq = json.loads(result.dlq_payload)
        assert "INVALID_CURRENCY" in dlq["failure_reason"]
        assert dlq["provider_event_id"] == "evt_123"

    def test_process_missing_required_fields(self, handler):
        """Test processing event with missing fields goes to DLQ."""
        event = {
            "id": "evt_123",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_123",
                    # Missing amount and currency
                    "created": 1700000000,
                }
            },
        }
        result = handler.process(
            raw_value=json.dumps(event).encode("utf-8"),
            source_topic="webhooks.stripe.payment_intent",
            partition=0,
            offset=100,
        )

        assert result.is_valid is False
        assert result.dlq_payload is not None

        dlq = json.loads(result.dlq_payload)
        assert len(dlq["validation_errors"]) >= 1

    def test_dlq_payload_contains_original(self, handler):
        """Test DLQ payload contains original payload."""
        invalid_event = {"id": "evt_123", "invalid": True}
        raw_value = json.dumps(invalid_event).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.stripe.payment_intent",
            partition=1,
            offset=999,
        )

        assert result.is_valid is False
        dlq = json.loads(result.dlq_payload)
        assert dlq["original_payload"] == json.dumps(invalid_event)

    def test_dlq_payload_has_timestamp(self, handler):
        """Test DLQ payload has quarantined_at timestamp."""
        event = {"id": "evt_123", "invalid": True}

        result = handler.process(
            raw_value=json.dumps(event).encode("utf-8"),
            source_topic="webhooks.stripe.payment_intent",
            partition=0,
            offset=100,
        )

        dlq = json.loads(result.dlq_payload)
        assert "quarantined_at" in dlq
        # Should be ISO format timestamp
        assert "T" in dlq["quarantined_at"]

    def test_dlq_payload_has_schema_version(self, handler):
        """Test DLQ payload has schema_version."""
        event = {"id": "evt_123", "invalid": True}

        result = handler.process(
            raw_value=json.dumps(event).encode("utf-8"),
            source_topic="webhooks.stripe.payment_intent",
            partition=0,
            offset=100,
        )

        dlq = json.loads(result.dlq_payload)
        assert dlq["schema_version"] == 1

    def test_event_id_prefixed_in_dlq(self, handler):
        """Test event_id is prefixed with provider in DLQ."""
        event = {
            "id": "evt_123",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_123",
                    "amount": -100,  # Invalid
                    "currency": "usd",
                    "created": 1700000000,
                }
            },
        }

        result = handler.process(
            raw_value=json.dumps(event).encode("utf-8"),
            source_topic="webhooks.stripe.payment_intent",
            partition=0,
            offset=100,
        )

        dlq = json.loads(result.dlq_payload)
        assert dlq["event_id"] == "stripe:evt_123"
        assert dlq["provider_event_id"] == "evt_123"

    def test_empty_event_id_in_dlq(self, handler):
        """Test handling event without ID in DLQ."""
        event = {
            # No id
            "type": "payment_intent.succeeded",
            "data": {"object": {}},
        }

        result = handler.process(
            raw_value=json.dumps(event).encode("utf-8"),
            source_topic="webhooks.stripe.payment_intent",
            partition=0,
            offset=100,
        )

        dlq = json.loads(result.dlq_payload)
        assert dlq["event_id"] is None
        assert dlq["provider_event_id"] is None
