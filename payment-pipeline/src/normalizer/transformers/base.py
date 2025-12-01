"""Base transformer and unified payment event schema."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class UnifiedPaymentEvent(BaseModel):
    """
    Provider-agnostic payment event schema.

    This is the canonical format that all payment events are normalized to,
    regardless of the original provider (Stripe, Square, etc.).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        ser_json_timedelta="iso8601",
    )

    # Core identifiers
    event_id: str = Field(..., description="Unique event ID (provider:original_id)")
    provider: str = Field(..., description="Payment provider (stripe, square, etc.)")
    provider_event_id: str = Field(..., description="Original event ID from provider")
    event_type: str = Field(..., description="Normalized event type")

    # Entity references
    merchant_id: str | None = Field(default=None, description="Merchant identifier")
    customer_id: str | None = Field(default=None, description="Customer identifier")

    # Payment details
    amount_cents: int = Field(..., ge=0, description="Amount in smallest currency unit")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO 4217 currency code")

    # Payment method info
    payment_method_type: str | None = Field(default=None, description="Payment method type")
    card_brand: str | None = Field(default=None, description="Card brand (visa, mastercard)")
    card_last_four: str | None = Field(default=None, description="Last 4 digits of card")

    # Status
    status: str = Field(..., description="Payment status")
    failure_code: str | None = Field(default=None, description="Failure code if failed")
    failure_message: str | None = Field(default=None, description="Failure message if failed")

    # Additional data
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    # Timestamps
    provider_created_at: datetime = Field(..., description="When provider created the event")
    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When normalizer processed the event",
    )

    # Schema version for evolution
    schema_version: int = Field(default=1, description="Schema version for compatibility")

    @field_serializer("provider_created_at", "processed_at")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime to ISO 8601 format."""
        return value.isoformat()


# Event type mappings for normalization
STRIPE_EVENT_TYPE_MAP = {
    # Payment intents
    "payment_intent.created": "payment.created",
    "payment_intent.succeeded": "payment.succeeded",
    "payment_intent.payment_failed": "payment.failed",
    "payment_intent.canceled": "payment.canceled",
    "payment_intent.processing": "payment.processing",
    "payment_intent.requires_action": "payment.requires_action",
    "payment_intent.amount_capturable_updated": "payment.amount_capturable_updated",
    # Charges
    "charge.succeeded": "charge.succeeded",
    "charge.failed": "charge.failed",
    "charge.pending": "charge.pending",
    "charge.captured": "charge.captured",
    "charge.refunded": "charge.refunded",
    "charge.updated": "charge.updated",
    "charge.dispute.created": "dispute.created",
    "charge.dispute.closed": "dispute.closed",
    # Refunds
    "refund.created": "refund.created",
    "refund.updated": "refund.updated",
    "refund.failed": "refund.failed",
}

SQUARE_EVENT_TYPE_MAP = {
    # Payments
    "payment.created": "payment.created",
    "payment.updated": "payment.updated",
    "payment.completed": "payment.succeeded",
    # Refunds
    "refund.created": "refund.created",
    "refund.updated": "refund.updated",
}


def normalize_event_type(provider: str, raw_type: str) -> str:
    """
    Normalize provider-specific event type to unified format.

    Args:
        provider: Payment provider name
        raw_type: Raw event type from provider

    Returns:
        Normalized event type
    """
    if provider == "stripe":
        return STRIPE_EVENT_TYPE_MAP.get(raw_type, raw_type)
    elif provider == "square":
        return SQUARE_EVENT_TYPE_MAP.get(raw_type, raw_type)
    return raw_type
