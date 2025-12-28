"""Unit tests for Square event transformer."""

import json

import pytest

from transformer.transformers.square import SquareTransformer


class TestSquareTransformer:
    """Tests for SquareTransformer class."""

    @pytest.fixture
    def transformer(self):
        """Create a SquareTransformer instance."""
        return SquareTransformer()

    def test_transform_valid_payment_event(self, transformer, valid_square_payment_event):
        """Test transforming a valid payment.completed event."""
        unified_event, result = transformer.transform(valid_square_payment_event)

        assert result.is_valid is True
        assert unified_event is not None
        assert unified_event.event_id == "square:evt_square_12345678"
        assert unified_event.provider == "square"
        assert unified_event.provider_event_id == "evt_square_12345678"
        assert unified_event.event_type == "payment.succeeded"  # Normalized from payment.completed
        assert unified_event.amount_cents == 2000
        assert unified_event.currency == "USD"
        assert unified_event.status == "succeeded"
        assert unified_event.customer_id == "CUS_1234567890"
        assert unified_event.merchant_id == "MERCHANT123456789"
        assert unified_event.card_brand == "VISA"
        assert unified_event.card_last_four == "4242"
        assert unified_event.payment_method_type == "card"

    def test_transform_valid_refund_event(self, transformer, valid_square_refund_event):
        """Test transforming a valid refund.created event."""
        unified_event, result = transformer.transform(valid_square_refund_event)

        assert result.is_valid is True
        assert unified_event is not None
        assert unified_event.event_id == "square:evt_square_refund_123"
        assert unified_event.provider == "square"
        assert unified_event.event_type == "refund.created"
        assert unified_event.amount_cents == 1000
        assert unified_event.currency == "USD"
        assert unified_event.status == "pending"
        assert unified_event.payment_method_type == "refund"

    def test_transform_missing_event_id(self, transformer, valid_square_payment_event):
        """Test that missing event_id causes validation failure."""
        event = valid_square_payment_event.copy()
        del event["event_id"]

        unified_event, result = transformer.transform(event)

        assert result.is_valid is False
        assert "MISSING_EVENT_ID" in result.error_codes
        assert unified_event is None

    def test_transform_missing_event_type(self, transformer, valid_square_payment_event):
        """Test that missing event type causes validation failure."""
        event = valid_square_payment_event.copy()
        del event["type"]

        unified_event, result = transformer.transform(event)

        assert result.is_valid is False
        assert "MISSING_EVENT_TYPE" in result.error_codes

    def test_transform_missing_data(self, transformer):
        """Test that missing data object causes validation failure."""
        event = {
            "merchant_id": "MERCHANT123",
            "type": "payment.completed",
            "event_id": "evt_123",
            "created_at": "2024-01-15T12:00:00Z",
        }

        unified_event, result = transformer.transform(event)

        assert result.is_valid is False
        assert "MISSING_DATA" in result.error_codes
        assert unified_event is None

    def test_transform_invalid_currency(self, transformer, valid_square_payment_event):
        """Test that invalid currency causes validation failure."""
        event = valid_square_payment_event.copy()
        event["data"]["object"]["payment"]["amount_money"]["currency"] = "XYZ"

        unified_event, result = transformer.transform(event)

        assert result.is_valid is False
        assert "INVALID_CURRENCY" in result.error_codes
        assert unified_event is None

    def test_transform_negative_amount(self, transformer, valid_square_payment_event):
        """Test that negative amount causes validation failure."""
        event = valid_square_payment_event.copy()
        event["data"]["object"]["payment"]["amount_money"]["amount"] = -100

        unified_event, result = transformer.transform(event)

        assert result.is_valid is False
        assert any("INVALID_AMOUNT" in code for code in result.error_codes)
        assert unified_event is None

    def test_transform_normalizes_status(self, transformer, valid_square_payment_event):
        """Test that Square statuses are normalized correctly."""
        # Test APPROVED -> approved
        event = valid_square_payment_event.copy()
        event["data"]["object"]["payment"]["status"] = "APPROVED"

        unified_event, result = transformer.transform(event)

        assert result.is_valid is True
        assert unified_event.status == "approved"

    def test_transform_extracts_metadata(self, transformer, valid_square_payment_event):
        """Test that metadata is correctly extracted."""
        unified_event, result = transformer.transform(valid_square_payment_event)

        assert result.is_valid is True
        assert unified_event.metadata.get("location_id") == "LOC_1234567890"
        assert unified_event.metadata.get("order_id") == "ORD_1234567890"

    def test_transform_handles_missing_card_details(self, transformer, valid_square_payment_event):
        """Test handling of events without card details."""
        event = valid_square_payment_event.copy()
        del event["data"]["object"]["payment"]["card_details"]

        unified_event, result = transformer.transform(event)

        assert result.is_valid is True
        assert unified_event.card_brand is None
        assert unified_event.card_last_four is None

    def test_transform_normalizes_source_type(self, transformer, valid_square_payment_event):
        """Test that source_type is normalized to payment_method_type."""
        event = valid_square_payment_event.copy()
        event["data"]["object"]["payment"]["source_type"] = "WALLET"

        unified_event, result = transformer.transform(event)

        assert result.is_valid is True
        assert unified_event.payment_method_type == "wallet"
