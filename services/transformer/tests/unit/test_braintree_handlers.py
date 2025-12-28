"""Unit tests for Braintree message handler."""

import json

import pytest

from transformer.handlers.braintree import BraintreeHandler, ProcessingResult


class TestBraintreeHandler:
    """Tests for BraintreeHandler class."""

    @pytest.fixture
    def handler(self):
        """Create a BraintreeHandler instance."""
        return BraintreeHandler()

    def test_process_valid_transaction_settled(self, handler, valid_braintree_transaction_settled):
        """Test processing a valid transaction_settled notification."""
        raw_value = json.dumps(valid_braintree_transaction_settled).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.braintree.notification",
            partition=0,
            offset=100,
        )

        assert result.is_valid is True
        assert result.normalized_payload is not None
        assert result.dlq_payload is None
        assert result.event_id == "braintree:transaction_settled_txn_1234567890"

        # Verify normalized payload structure
        payload = json.loads(result.normalized_payload)
        assert payload["provider"] == "braintree"
        assert payload["event_type"] == "payment.settled"
        assert payload["amount_cents"] == 2000
        assert payload["currency"] == "USD"

    def test_process_valid_subscription_charged(self, handler, valid_braintree_subscription_charged):
        """Test processing a valid subscription_charged_successfully notification."""
        raw_value = json.dumps(valid_braintree_subscription_charged).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.braintree.notification",
            partition=0,
            offset=101,
        )

        assert result.is_valid is True
        assert result.normalized_payload is not None

        payload = json.loads(result.normalized_payload)
        assert payload["event_type"] == "subscription.charged"
        assert payload["status"] == "succeeded"

    def test_process_valid_dispute_opened(self, handler, valid_braintree_dispute_opened):
        """Test processing a valid dispute_opened notification."""
        raw_value = json.dumps(valid_braintree_dispute_opened).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.braintree.notification",
            partition=0,
            offset=102,
        )

        assert result.is_valid is True
        assert result.normalized_payload is not None

        payload = json.loads(result.normalized_payload)
        assert payload["event_type"] == "dispute.created"
        assert payload["status"] == "disputed"

    def test_process_invalid_json(self, handler):
        """Test that invalid JSON goes to DLQ."""
        raw_value = b"not valid json {"

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.braintree.notification",
            partition=0,
            offset=103,
        )

        assert result.is_valid is False
        assert result.normalized_payload is None
        assert result.dlq_payload is not None

        dlq = json.loads(result.dlq_payload)
        assert dlq["provider"] == "braintree"
        assert dlq["failure_reason"] == "INVALID_JSON"
        assert dlq["source_topic"] == "webhooks.braintree.notification"

    def test_process_missing_required_field(self, handler, valid_braintree_transaction_settled):
        """Test that missing required fields go to DLQ."""
        event = valid_braintree_transaction_settled.copy()
        del event["kind"]
        raw_value = json.dumps(event).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.braintree.notification",
            partition=0,
            offset=104,
        )

        assert result.is_valid is False
        assert result.dlq_payload is not None

        dlq = json.loads(result.dlq_payload)
        assert dlq["failure_reason"] == "MISSING_KIND"

    def test_process_invalid_currency(self, handler, valid_braintree_transaction_settled):
        """Test that invalid currency goes to DLQ."""
        event = valid_braintree_transaction_settled.copy()
        event["transaction"]["currency_iso_code"] = "INVALID"
        raw_value = json.dumps(event).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.braintree.notification",
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
            source_topic="webhooks.braintree.notification",
            partition=1,
            offset=200,
        )

        assert result.dlq_payload is not None
        dlq = json.loads(result.dlq_payload)

        # Check required DLQ fields
        assert "provider" in dlq
        assert dlq["provider"] == "braintree"
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

    def test_event_id_format(self, handler, valid_braintree_transaction_settled):
        """Test that event ID follows expected format."""
        raw_value = json.dumps(valid_braintree_transaction_settled).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.braintree.notification",
            partition=0,
            offset=107,
        )

        # Event ID should be braintree:{kind}_{transaction_id}
        assert result.event_id == "braintree:transaction_settled_txn_1234567890"

        payload = json.loads(result.normalized_payload)
        assert payload["event_id"] == "braintree:transaction_settled_txn_1234567890"

    def test_process_disbursement_event(self, handler):
        """Test processing a disbursement event."""
        event = {
            "kind": "disbursement",
            "timestamp": "2024-01-15T16:00:00+00:00",
            "transaction": {
                "id": "txn_disbursement_123",
                "status": "settled",
                "type": "sale",
                "amount": "100.00",
                "currency_iso_code": "USD",
                "merchant_account_id": "merchant_123",
            },
        }
        raw_value = json.dumps(event).encode("utf-8")

        result = handler.process(
            raw_value=raw_value,
            source_topic="webhooks.braintree.notification",
            partition=0,
            offset=108,
        )

        assert result.is_valid is True
        payload = json.loads(result.normalized_payload)
        assert payload["event_type"] == "disbursement.created"
        assert payload["status"] == "disbursed"
