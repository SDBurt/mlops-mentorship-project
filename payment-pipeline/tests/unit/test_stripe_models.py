"""Unit tests for Stripe Pydantic models."""

import pytest
from pydantic import ValidationError

from payment_gateway.providers.stripe.models import (
    StripeChargeData,
    StripeChargeEvent,
    StripePaymentIntentData,
    StripePaymentIntentEvent,
    StripeWebhookEventAdapter,
    get_stripe_event_discriminator,
)


class TestStripePaymentIntentData:
    """Tests for StripePaymentIntentData model."""

    def test_valid_payment_intent_data(self):
        """Test valid payment intent data parsing."""
        data = {
            "id": "pi_1234567890abcdef",
            "object": "payment_intent",
            "amount": 2000,
            "currency": "USD",
            "status": "succeeded",
            "created": 1700000000,
        }
        result = StripePaymentIntentData.model_validate(data)
        assert result.id == "pi_1234567890abcdef"
        assert result.amount == 2000
        assert result.currency == "usd"  # Should be lowercased
        assert result.status == "succeeded"

    def test_invalid_payment_intent_id_pattern(self):
        """Test that invalid ID patterns are rejected."""
        data = {
            "id": "invalid_id",  # Should start with pi_
            "object": "payment_intent",
            "amount": 2000,
            "currency": "usd",
            "status": "succeeded",
            "created": 1700000000,
        }
        with pytest.raises(ValidationError) as exc_info:
            StripePaymentIntentData.model_validate(data)
        assert "id" in str(exc_info.value)

    def test_negative_amount_rejected(self):
        """Test that negative amounts are rejected."""
        data = {
            "id": "pi_1234567890abcdef",
            "object": "payment_intent",
            "amount": -100,  # Should be >= 0
            "currency": "usd",
            "status": "succeeded",
            "created": 1700000000,
        }
        with pytest.raises(ValidationError) as exc_info:
            StripePaymentIntentData.model_validate(data)
        assert "amount" in str(exc_info.value)

    def test_currency_validation(self):
        """Test currency code validation."""
        data = {
            "id": "pi_1234567890abcdef",
            "object": "payment_intent",
            "amount": 2000,
            "currency": "INVALID",  # Should be 3 chars
            "status": "succeeded",
            "created": 1700000000,
        }
        with pytest.raises(ValidationError):
            StripePaymentIntentData.model_validate(data)


class TestStripeChargeData:
    """Tests for StripeChargeData model."""

    def test_valid_charge_data(self):
        """Test valid charge data parsing."""
        data = {
            "id": "ch_1234567890abcdef",
            "object": "charge",
            "amount": 2000,
            "currency": "EUR",
            "status": "succeeded",
            "paid": True,
            "captured": True,
            "created": 1700000000,
        }
        result = StripeChargeData.model_validate(data)
        assert result.id == "ch_1234567890abcdef"
        assert result.currency == "eur"  # Should be lowercased
        assert result.paid is True

    def test_invalid_charge_id_pattern(self):
        """Test that invalid charge ID patterns are rejected."""
        data = {
            "id": "pi_1234567890abcdef",  # Should start with ch_
            "object": "charge",
            "amount": 2000,
            "currency": "usd",
            "status": "succeeded",
            "paid": True,
            "captured": True,
            "created": 1700000000,
        }
        with pytest.raises(ValidationError):
            StripeChargeData.model_validate(data)


class TestStripePaymentIntentEvent:
    """Tests for full payment intent event parsing."""

    def test_valid_payment_intent_succeeded_event(self, valid_payment_intent_event):
        """Test parsing a valid payment_intent.succeeded event."""
        event = StripePaymentIntentEvent.model_validate(valid_payment_intent_event)
        assert event.id == "evt_1234567890abcdef"
        assert event.type == "payment_intent.succeeded"
        assert event.data.object.amount == 2000
        assert event.event_category == "payment_intent"

    def test_invalid_event_type(self, valid_payment_intent_event):
        """Test that invalid event types are rejected."""
        valid_payment_intent_event["type"] = "invalid.event.type"
        with pytest.raises(ValidationError):
            StripePaymentIntentEvent.model_validate(valid_payment_intent_event)


class TestStripeChargeEvent:
    """Tests for full charge event parsing."""

    def test_valid_charge_succeeded_event(self, valid_charge_event):
        """Test parsing a valid charge.succeeded event."""
        event = StripeChargeEvent.model_validate(valid_charge_event)
        assert event.id == "evt_charge12345678"
        assert event.type == "charge.succeeded"
        assert event.data.object.amount == 2000
        assert event.event_category == "charge"


class TestDiscriminatedUnion:
    """Tests for the discriminated union routing."""

    def test_discriminator_payment_intent(self):
        """Test discriminator routes payment_intent events correctly."""
        assert get_stripe_event_discriminator({"type": "payment_intent.succeeded"}) == "payment_intent"
        assert get_stripe_event_discriminator({"type": "payment_intent.failed"}) == "payment_intent"

    def test_discriminator_charge(self):
        """Test discriminator routes charge events correctly."""
        assert get_stripe_event_discriminator({"type": "charge.succeeded"}) == "charge"
        assert get_stripe_event_discriminator({"type": "charge.failed"}) == "charge"

    def test_discriminator_refund(self):
        """Test discriminator routes refund events correctly."""
        assert get_stripe_event_discriminator({"type": "refund.created"}) == "refund"

    def test_discriminator_unknown(self):
        """Test discriminator handles unknown events."""
        assert get_stripe_event_discriminator({"type": "unknown.event"}) == "unknown"

    def test_union_routes_to_payment_intent(self, valid_payment_intent_event):
        """Test that the union correctly parses payment_intent events."""
        event = StripeWebhookEventAdapter.validate_python(valid_payment_intent_event)
        assert isinstance(event, StripePaymentIntentEvent)

    def test_union_routes_to_charge(self, valid_charge_event):
        """Test that the union correctly parses charge events."""
        event = StripeWebhookEventAdapter.validate_python(valid_charge_event)
        assert isinstance(event, StripeChargeEvent)
