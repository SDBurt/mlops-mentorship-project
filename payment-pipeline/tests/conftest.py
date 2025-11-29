"""Pytest fixtures for payment gateway tests."""

import pytest


@pytest.fixture
def stripe_webhook_secret() -> str:
    """Test webhook signing secret."""
    return "whsec_test_secret_12345"


@pytest.fixture
def valid_payment_intent_event() -> dict:
    """A valid payment_intent.succeeded event payload."""
    return {
        "id": "evt_1234567890abcdef",
        "object": "event",
        "api_version": "2024-09-30.acacia",
        "created": 1700000000,
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_1234567890abcdef",
                "object": "payment_intent",
                "amount": 2000,
                "amount_capturable": 0,
                "amount_received": 2000,
                "currency": "usd",
                "status": "succeeded",
                "customer": "cus_1234567890ab",
                "payment_method": "pm_1234567890abcdefgh",
                "payment_method_types": ["card"],
                "description": "Test payment",
                "metadata": {"order_id": "ord_123"},
                "created": 1700000000,
                "livemode": False,
                "last_payment_error": None,
                "cancellation_reason": None,
            },
            "previous_attributes": None,
        },
        "livemode": False,
        "pending_webhooks": 1,
        "request": {
            "id": "req_1234567890ab",
            "idempotency_key": None,
        },
    }


@pytest.fixture
def valid_charge_event() -> dict:
    """A valid charge.succeeded event payload."""
    return {
        "id": "evt_charge12345678",
        "object": "event",
        "api_version": "2024-09-30.acacia",
        "created": 1700000000,
        "type": "charge.succeeded",
        "data": {
            "object": {
                "id": "ch_1234567890abcdef",
                "object": "charge",
                "amount": 2000,
                "amount_captured": 2000,
                "amount_refunded": 0,
                "currency": "usd",
                "status": "succeeded",
                "paid": True,
                "captured": True,
                "refunded": False,
                "disputed": False,
                "customer": "cus_1234567890ab",
                "payment_intent": "pi_1234567890abcdef",
                "payment_method": "pm_1234567890abcdefgh",
                "payment_method_details": {
                    "card": {
                        "brand": "visa",
                        "last4": "4242",
                        "exp_month": 12,
                        "exp_year": 2025,
                        "country": "US",
                    }
                },
                "failure_code": None,
                "failure_message": None,
                "description": "Test charge",
                "metadata": {},
                "created": 1700000000,
                "livemode": False,
            },
            "previous_attributes": None,
        },
        "livemode": False,
        "pending_webhooks": 1,
        "request": {
            "id": "req_charge1234567",
            "idempotency_key": None,
        },
    }
