"""Unit tests for normalizer transformers."""

import pytest
from datetime import datetime, timezone

from normalizer.transformers.stripe import StripeTransformer
from normalizer.transformers.base import (
    UnifiedPaymentEvent,
    normalize_event_type,
    STRIPE_EVENT_TYPE_MAP,
)


class TestUnifiedPaymentEvent:
    """Tests for the UnifiedPaymentEvent schema."""

    def test_valid_event_creation(self):
        """Test creating a valid unified payment event."""
        event = UnifiedPaymentEvent(
            event_id="stripe:evt_123",
            provider="stripe",
            provider_event_id="evt_123",
            event_type="payment.succeeded",
            amount_cents=2000,
            currency="USD",
            status="succeeded",
            provider_created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert event.event_id == "stripe:evt_123"
        assert event.provider == "stripe"
        assert event.amount_cents == 2000
        assert event.currency == "USD"
        assert event.schema_version == 1

    def test_optional_fields_default_to_none(self):
        """Test that optional fields default to None."""
        event = UnifiedPaymentEvent(
            event_id="stripe:evt_123",
            provider="stripe",
            provider_event_id="evt_123",
            event_type="payment.succeeded",
            amount_cents=2000,
            currency="USD",
            status="succeeded",
            provider_created_at=datetime.now(timezone.utc),
        )
        assert event.merchant_id is None
        assert event.customer_id is None
        assert event.payment_method_type is None
        assert event.card_brand is None
        assert event.card_last_four is None
        assert event.failure_code is None
        assert event.failure_message is None

    def test_metadata_defaults_to_empty_dict(self):
        """Test that metadata defaults to empty dict."""
        event = UnifiedPaymentEvent(
            event_id="stripe:evt_123",
            provider="stripe",
            provider_event_id="evt_123",
            event_type="payment.succeeded",
            amount_cents=2000,
            currency="USD",
            status="succeeded",
            provider_created_at=datetime.now(timezone.utc),
        )
        assert event.metadata == {}

    def test_processed_at_auto_generated(self):
        """Test that processed_at is auto-generated."""
        before = datetime.now(timezone.utc)
        event = UnifiedPaymentEvent(
            event_id="stripe:evt_123",
            provider="stripe",
            provider_event_id="evt_123",
            event_type="payment.succeeded",
            amount_cents=2000,
            currency="USD",
            status="succeeded",
            provider_created_at=datetime.now(timezone.utc),
        )
        after = datetime.now(timezone.utc)
        assert before <= event.processed_at <= after

    def test_amount_must_be_non_negative(self):
        """Test that negative amounts are rejected by pydantic."""
        with pytest.raises(ValueError):
            UnifiedPaymentEvent(
                event_id="stripe:evt_123",
                provider="stripe",
                provider_event_id="evt_123",
                event_type="payment.succeeded",
                amount_cents=-100,
                currency="USD",
                status="succeeded",
                provider_created_at=datetime.now(timezone.utc),
            )

    def test_currency_must_be_3_chars(self):
        """Test that currency must be 3 characters."""
        with pytest.raises(ValueError):
            UnifiedPaymentEvent(
                event_id="stripe:evt_123",
                provider="stripe",
                provider_event_id="evt_123",
                event_type="payment.succeeded",
                amount_cents=100,
                currency="US",  # Too short
                status="succeeded",
                provider_created_at=datetime.now(timezone.utc),
            )

    def test_json_serialization(self):
        """Test that events serialize to JSON correctly."""
        event = UnifiedPaymentEvent(
            event_id="stripe:evt_123",
            provider="stripe",
            provider_event_id="evt_123",
            event_type="payment.succeeded",
            amount_cents=2000,
            currency="USD",
            status="succeeded",
            provider_created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
        json_str = event.model_dump_json()
        assert "stripe:evt_123" in json_str
        assert "USD" in json_str
        assert "2000" in json_str


class TestNormalizeEventType:
    """Tests for event type normalization."""

    def test_stripe_event_types_mapped(self):
        """Test that Stripe event types are correctly mapped."""
        assert normalize_event_type("stripe", "payment_intent.succeeded") == "payment.succeeded"
        assert normalize_event_type("stripe", "payment_intent.payment_failed") == "payment.failed"
        assert normalize_event_type("stripe", "charge.succeeded") == "charge.succeeded"
        assert normalize_event_type("stripe", "refund.created") == "refund.created"

    def test_unknown_stripe_event_preserved(self):
        """Test that unknown Stripe events are preserved."""
        assert normalize_event_type("stripe", "unknown.event") == "unknown.event"

    def test_non_stripe_events_preserved(self):
        """Test that non-Stripe events are passed through."""
        assert normalize_event_type("square", "payment.completed") == "payment.completed"

    def test_all_mapped_event_types(self):
        """Test that all mapped event types are covered."""
        for raw_type, normalized in STRIPE_EVENT_TYPE_MAP.items():
            result = normalize_event_type("stripe", raw_type)
            assert result == normalized


class TestStripeTransformer:
    """Tests for Stripe event transformation."""

    @pytest.fixture
    def transformer(self):
        """Create a StripeTransformer instance."""
        return StripeTransformer()

    @pytest.fixture
    def valid_payment_intent(self):
        """A valid payment_intent.succeeded event."""
        return {
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
                    "metadata": {"order_id": "123", "merchant_id": "merchant_abc"},
                    "created": 1700000000,
                }
            },
        }

    @pytest.fixture
    def valid_charge_event(self):
        """A valid charge.succeeded event."""
        return {
            "id": "evt_charge12345678",
            "type": "charge.succeeded",
            "created": 1700000000,
            "data": {
                "object": {
                    "id": "ch_1234567890abcdef",
                    "amount": 2000,
                    "currency": "usd",
                    "status": "succeeded",
                    "customer": "cus_123",
                    "payment_method_details": {
                        "type": "card",
                        "card": {
                            "brand": "visa",
                            "last4": "4242",
                        },
                    },
                    "metadata": {},
                    "created": 1700000000,
                }
            },
        }

    def test_transform_valid_payment_intent(self, transformer, valid_payment_intent):
        """Test transforming a valid payment_intent event."""
        unified, result = transformer.transform(valid_payment_intent)

        assert result.is_valid is True
        assert unified is not None
        assert unified.event_id == "stripe:evt_1234567890abcdef"
        assert unified.provider == "stripe"
        assert unified.provider_event_id == "evt_1234567890abcdef"
        assert unified.event_type == "payment.succeeded"
        assert unified.amount_cents == 2000
        assert unified.currency == "USD"
        assert unified.status == "succeeded"
        assert unified.customer_id == "cus_123"
        assert unified.merchant_id == "merchant_abc"
        assert unified.payment_method_type == "card"

    def test_transform_valid_charge(self, transformer, valid_charge_event):
        """Test transforming a valid charge event."""
        unified, result = transformer.transform(valid_charge_event)

        assert result.is_valid is True
        assert unified is not None
        assert unified.event_type == "charge.succeeded"
        assert unified.card_brand == "visa"
        assert unified.card_last_four == "4242"
        assert unified.payment_method_type == "card"

    def test_missing_event_id_invalid(self, transformer):
        """Test that missing event ID causes validation failure."""
        event = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_123", "amount": 100, "currency": "usd"}},
        }
        unified, result = transformer.transform(event)
        assert result.is_valid is False
        assert "MISSING_EVENT_ID" in result.error_codes

    def test_missing_event_type_invalid(self, transformer):
        """Test that missing event type causes validation failure."""
        event = {
            "id": "evt_123",
            "data": {"object": {"id": "pi_123", "amount": 100, "currency": "usd"}},
        }
        unified, result = transformer.transform(event)
        assert result.is_valid is False
        assert "MISSING_EVENT_TYPE" in result.error_codes

    def test_missing_data_object_invalid(self, transformer):
        """Test that missing data.object causes validation failure."""
        event = {
            "id": "evt_123",
            "type": "payment_intent.succeeded",
            "data": {},
        }
        unified, result = transformer.transform(event)
        assert result.is_valid is False
        assert unified is None
        assert "MISSING_DATA_OBJECT" in result.error_codes

    def test_missing_amount_invalid(self, transformer):
        """Test that missing amount causes validation failure."""
        event = {
            "id": "evt_123",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_123",
                    "currency": "usd",
                    "created": 1700000000,
                }
            },
        }
        unified, result = transformer.transform(event)
        assert result.is_valid is False
        assert "INVALID_AMOUNT" in result.error_codes

    def test_negative_amount_invalid(self, transformer):
        """Test that negative amounts cause validation failure."""
        event = {
            "id": "evt_123",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_123",
                    "amount": -100,
                    "currency": "usd",
                    "created": 1700000000,
                }
            },
        }
        unified, result = transformer.transform(event)
        assert result.is_valid is False
        assert "INVALID_AMOUNT_NEGATIVE" in result.error_codes

    def test_amount_too_large_invalid(self, transformer):
        """Test that amounts over max cause validation failure."""
        event = {
            "id": "evt_123",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_123",
                    "amount": 999_999_999_999,  # Way over max
                    "currency": "usd",
                    "created": 1700000000,
                }
            },
        }
        unified, result = transformer.transform(event)
        assert result.is_valid is False
        assert "INVALID_AMOUNT_TOO_LARGE" in result.error_codes

    def test_missing_currency_invalid(self, transformer):
        """Test that missing currency causes validation failure."""
        event = {
            "id": "evt_123",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_123",
                    "amount": 100,
                    "created": 1700000000,
                }
            },
        }
        unified, result = transformer.transform(event)
        assert result.is_valid is False
        assert "INVALID_CURRENCY" in result.error_codes

    def test_unsupported_currency_invalid(self, transformer):
        """Test that unsupported currency causes validation failure."""
        event = {
            "id": "evt_123",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_123",
                    "amount": 100,
                    "currency": "xyz",
                    "created": 1700000000,
                }
            },
        }
        unified, result = transformer.transform(event)
        assert result.is_valid is False
        assert "INVALID_CURRENCY" in result.error_codes

    def test_currency_normalized_to_uppercase(self, transformer, valid_payment_intent):
        """Test that currency is normalized to uppercase."""
        unified, result = transformer.transform(valid_payment_intent)
        assert result.is_valid is True
        assert unified.currency == "USD"

    def test_null_customer_normalized(self, transformer):
        """Test that null string customer is normalized to None."""
        event = {
            "id": "evt_123",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_123",
                    "amount": 100,
                    "currency": "usd",
                    "customer": "null",  # Null string
                    "created": 1700000000,
                }
            },
        }
        unified, result = transformer.transform(event)
        assert result.is_valid is True
        assert unified.customer_id is None

    def test_status_extracted_from_data_object(self, transformer, valid_payment_intent):
        """Test that status is extracted from data.object."""
        unified, result = transformer.transform(valid_payment_intent)
        assert unified.status == "succeeded"

    def test_status_inferred_from_event_type(self, transformer):
        """Test that status is inferred from event type when not present."""
        event = {
            "id": "evt_123",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_123",
                    "amount": 100,
                    "currency": "usd",
                    "created": 1700000000,
                    # No status field
                }
            },
        }
        unified, result = transformer.transform(event)
        assert result.is_valid is True
        assert unified.status == "succeeded"

    def test_failure_info_extracted(self, transformer):
        """Test that failure information is extracted."""
        event = {
            "id": "evt_123",
            "type": "charge.failed",
            "data": {
                "object": {
                    "id": "ch_123",
                    "amount": 100,
                    "currency": "usd",
                    "status": "failed",
                    "failure_code": "card_declined",
                    "failure_message": "Your card was declined.",
                    "created": 1700000000,
                }
            },
        }
        unified, result = transformer.transform(event)
        assert result.is_valid is True
        assert unified.failure_code == "card_declined"
        assert unified.failure_message == "Your card was declined."

    def test_payment_method_type_from_payment_method_types(self, transformer, valid_payment_intent):
        """Test payment method type extracted from payment_method_types array."""
        unified, result = transformer.transform(valid_payment_intent)
        assert unified.payment_method_type == "card"

    def test_payment_method_type_from_payment_method_details(self, transformer, valid_charge_event):
        """Test payment method type extracted from payment_method_details."""
        unified, result = transformer.transform(valid_charge_event)
        assert unified.payment_method_type == "card"

    def test_refund_defaults_to_refund_payment_type(self, transformer):
        """Test that refund events default to 'refund' payment type."""
        event = {
            "id": "evt_123",
            "type": "refund.created",
            "data": {
                "object": {
                    "id": "re_123",
                    "amount": 100,
                    "currency": "usd",
                    "created": 1700000000,
                }
            },
        }
        unified, result = transformer.transform(event)
        assert result.is_valid is True
        assert unified.payment_method_type == "refund"

    def test_card_details_extracted(self, transformer, valid_charge_event):
        """Test that card brand and last four are extracted."""
        unified, result = transformer.transform(valid_charge_event)
        assert unified.card_brand == "visa"
        assert unified.card_last_four == "4242"

    def test_timestamp_converted_to_datetime(self, transformer, valid_payment_intent):
        """Test that Unix timestamp is converted to datetime."""
        unified, result = transformer.transform(valid_payment_intent)
        assert isinstance(unified.provider_created_at, datetime)
        assert unified.provider_created_at.year == 2023

    def test_metadata_preserved(self, transformer, valid_payment_intent):
        """Test that metadata is preserved."""
        unified, result = transformer.transform(valid_payment_intent)
        assert unified.metadata == {"order_id": "123", "merchant_id": "merchant_abc"}

    def test_multiple_validation_errors(self, transformer):
        """Test that multiple validation errors are collected."""
        event = {
            # Missing id
            # Missing type
            "data": {
                "object": {
                    "id": "pi_123",
                    # Missing amount
                    # Missing currency
                    "created": 1700000000,
                }
            },
        }
        unified, result = transformer.transform(event)
        assert result.is_valid is False
        # Should have multiple errors
        assert len(result.errors) >= 2
        error_codes = result.error_codes
        assert "MISSING_EVENT_ID" in error_codes
        assert "MISSING_EVENT_TYPE" in error_codes
