"""Stripe webhook Pydantic models matching the real Stripe API structure."""

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Discriminator, Field, Tag, TypeAdapter, field_validator


# =============================================================================
# Nested Data Objects (data.object)
# =============================================================================


class StripePaymentIntentData(BaseModel):
    """Data object for payment_intent events (nested in data.object)."""

    id: str = Field(..., pattern=r"^pi_[a-zA-Z0-9]+$", description="Payment Intent ID")
    object: Literal["payment_intent"] = "payment_intent"
    amount: int = Field(..., ge=0, description="Amount in smallest currency unit (cents)")
    amount_capturable: int = Field(default=0, ge=0)
    amount_received: int = Field(default=0, ge=0)
    currency: str = Field(..., min_length=3, max_length=3, description="ISO 4217 currency code")
    status: Literal[
        "requires_payment_method",
        "requires_confirmation",
        "requires_action",
        "processing",
        "requires_capture",
        "canceled",
        "succeeded",
    ]
    customer: str | None = Field(default=None, pattern=r"^cus_[a-zA-Z0-9]+$")
    payment_method: str | None = Field(default=None, pattern=r"^pm_[a-zA-Z0-9]+$")
    payment_method_types: list[str] = Field(default_factory=list)
    description: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    created: int = Field(..., description="Unix timestamp")
    livemode: bool = False

    # Failure information (for failed payments)
    last_payment_error: dict[str, Any] | None = None
    cancellation_reason: str | None = None

    @field_validator("currency")
    @classmethod
    def lowercase_currency(cls, v: str) -> str:
        return v.lower()


class StripeChargeData(BaseModel):
    """Data object for charge events (nested in data.object)."""

    id: str = Field(..., pattern=r"^ch_[a-zA-Z0-9]+$", description="Charge ID")
    object: Literal["charge"] = "charge"
    amount: int = Field(..., ge=0, description="Amount in smallest currency unit")
    amount_captured: int = Field(default=0, ge=0)
    amount_refunded: int = Field(default=0, ge=0)
    currency: str = Field(..., min_length=3, max_length=3)
    status: Literal["succeeded", "pending", "failed"]
    paid: bool
    captured: bool
    refunded: bool = False
    disputed: bool = False

    customer: str | None = Field(default=None, pattern=r"^cus_[a-zA-Z0-9]+$")
    payment_intent: str | None = Field(default=None, pattern=r"^pi_[a-zA-Z0-9]+$")
    payment_method: str | None = Field(default=None, pattern=r"^pm_[a-zA-Z0-9]+$")

    # Card details (simplified)
    payment_method_details: dict[str, Any] | None = None

    # Failure information
    failure_code: str | None = None
    failure_message: str | None = None

    description: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    created: int = Field(..., description="Unix timestamp")
    livemode: bool = False

    @field_validator("currency")
    @classmethod
    def lowercase_currency(cls, v: str) -> str:
        return v.lower()


class StripeRefundData(BaseModel):
    """Data object for refund events (nested in data.object)."""

    id: str = Field(..., pattern=r"^re_[a-zA-Z0-9]+$", description="Refund ID")
    object: Literal["refund"] = "refund"
    amount: int = Field(..., ge=0)
    currency: str = Field(..., min_length=3, max_length=3)
    status: Literal["pending", "succeeded", "failed", "canceled"]
    charge: str | None = Field(default=None, pattern=r"^ch_[a-zA-Z0-9]+$")
    payment_intent: str | None = Field(default=None, pattern=r"^pi_[a-zA-Z0-9]+$")
    reason: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    created: int
    failure_reason: str | None = None

    @field_validator("currency")
    @classmethod
    def lowercase_currency(cls, v: str) -> str:
        return v.lower()


# =============================================================================
# Event Data Wrappers (data)
# =============================================================================


class StripePaymentIntentEventData(BaseModel):
    """Wrapper for payment_intent event data."""

    object: StripePaymentIntentData
    previous_attributes: dict[str, Any] | None = None


class StripeChargeEventData(BaseModel):
    """Wrapper for charge event data."""

    object: StripeChargeData
    previous_attributes: dict[str, Any] | None = None


class StripeRefundEventData(BaseModel):
    """Wrapper for refund event data."""

    object: StripeRefundData
    previous_attributes: dict[str, Any] | None = None


# =============================================================================
# Request Object
# =============================================================================


class StripeRequestObject(BaseModel):
    """Information about the API request that triggered the event."""

    id: str | None = Field(default=None, pattern=r"^req_[a-zA-Z0-9]+$")
    idempotency_key: str | None = None


# =============================================================================
# Main Event Models
# =============================================================================


class StripePaymentIntentEvent(BaseModel):
    """Stripe payment_intent.* webhook event."""

    id: str = Field(..., pattern=r"^evt_[a-zA-Z0-9]+$", description="Event ID")
    object: Literal["event"] = "event"
    api_version: str = Field(..., description="Stripe API version")
    created: int = Field(..., description="Unix timestamp")
    type: Literal[
        "payment_intent.created",
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
        "payment_intent.canceled",
        "payment_intent.processing",
        "payment_intent.requires_action",
        "payment_intent.amount_capturable_updated",
    ]
    data: StripePaymentIntentEventData
    livemode: bool
    pending_webhooks: int = Field(default=0, ge=0)
    request: StripeRequestObject | None = None

    @property
    def event_category(self) -> str:
        """Return the event category for Kafka topic routing."""
        return "payment_intent"


class StripeChargeEvent(BaseModel):
    """Stripe charge.* webhook event."""

    id: str = Field(..., pattern=r"^evt_[a-zA-Z0-9]+$")
    object: Literal["event"] = "event"
    api_version: str
    created: int
    type: Literal[
        "charge.succeeded",
        "charge.failed",
        "charge.pending",
        "charge.captured",
        "charge.refunded",
        "charge.updated",
        "charge.dispute.created",
        "charge.dispute.closed",
    ]
    data: StripeChargeEventData
    livemode: bool
    pending_webhooks: int = Field(default=0, ge=0)
    request: StripeRequestObject | None = None

    @property
    def event_category(self) -> str:
        return "charge"


class StripeRefundEvent(BaseModel):
    """Stripe refund.* webhook event."""

    id: str = Field(..., pattern=r"^evt_[a-zA-Z0-9]+$")
    object: Literal["event"] = "event"
    api_version: str
    created: int
    type: Literal[
        "refund.created",
        "refund.updated",
        "refund.failed",
    ]
    data: StripeRefundEventData
    livemode: bool
    pending_webhooks: int = Field(default=0, ge=0)
    request: StripeRequestObject | None = None

    @property
    def event_category(self) -> str:
        return "refund"


# =============================================================================
# Discriminated Union
# =============================================================================


def get_stripe_event_discriminator(v: Any) -> str:
    """
    Discriminator function to route events to the correct model based on type.

    Args:
        v: The raw value (dict or model instance)

    Returns:
        Tag string for discriminated union routing
    """
    if isinstance(v, dict):
        event_type = v.get("type", "")
    else:
        event_type = getattr(v, "type", "")

    if event_type.startswith("payment_intent."):
        return "payment_intent"
    elif event_type.startswith("charge."):
        return "charge"
    elif event_type.startswith("refund."):
        return "refund"
    return "unknown"


# Main discriminated union type for all Stripe webhook events
StripeWebhookEvent = Annotated[
    Union[
        Annotated[StripePaymentIntentEvent, Tag("payment_intent")],
        Annotated[StripeChargeEvent, Tag("charge")],
        Annotated[StripeRefundEvent, Tag("refund")],
    ],
    Discriminator(get_stripe_event_discriminator),
]

# TypeAdapter for validating the discriminated union
# Use this instead of calling .model_validate() on the type alias
StripeWebhookEventAdapter = TypeAdapter(StripeWebhookEvent)
