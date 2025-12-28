"""Pydantic models for Braintree webhook payloads."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BraintreeCardDetails(BaseModel):
    """Card details from Braintree transaction."""

    card_type: str | None = None
    last_4: str | None = Field(None, alias="last_4")


class BraintreeTransaction(BaseModel):
    """Braintree transaction data."""

    id: str
    status: str | None = None
    type: str | None = None
    amount: str | None = None
    currency_iso_code: str = "USD"
    merchant_account_id: str | None = None
    customer_id: str | None = None
    payment_instrument_type: str | None = None
    card_details: BraintreeCardDetails | None = None


class BraintreeSubscription(BaseModel):
    """Braintree subscription data."""

    id: str
    status: str | None = None
    plan_id: str | None = None


class BraintreeDispute(BaseModel):
    """Braintree dispute data."""

    id: str
    status: str | None = None
    reason: str | None = None
    amount: str | None = None


class BraintreeWebhookNotification(BaseModel):
    """Parsed Braintree webhook notification."""

    kind: str = Field(..., description="Notification kind (e.g., transaction_settled)")
    timestamp: str | None = Field(None, description="ISO 8601 timestamp")
    transaction: BraintreeTransaction | None = None
    subscription: BraintreeSubscription | None = None
    dispute: BraintreeDispute | None = None
    raw_payload: str | None = Field(None, description="Original bt_payload for reference")
    dev_mode: bool = Field(False, description="True if parsed in dev mode without verification")

    model_config = {"extra": "allow"}
