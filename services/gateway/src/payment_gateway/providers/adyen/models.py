"""Adyen webhook Pydantic models matching the real Adyen API structure."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class AdyenAmount(BaseModel):
    """Adyen amount object."""

    value: int = Field(..., ge=0, description="Amount in minor units (cents)")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO 4217 currency code")

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()


class AdyenNotificationItem(BaseModel):
    """Single Adyen notification item (NotificationRequestItem)."""

    # Required fields
    pspReference: str = Field(..., description="Adyen's unique reference for the payment")
    eventCode: str = Field(
        ...,
        description="Event type (AUTHORISATION, CAPTURE, REFUND, etc.)",
    )
    merchantAccountCode: str = Field(..., description="Merchant account code")
    amount: AdyenAmount = Field(..., description="Transaction amount")
    success: bool = Field(..., description="Whether the event was successful")

    # Optional fields
    originalReference: str | None = Field(default=None, description="Original payment reference")
    merchantReference: str | None = Field(default=None, description="Merchant's reference")
    eventDate: str | None = Field(default=None, description="Event timestamp")
    paymentMethod: str | None = Field(default=None, description="Payment method used")
    reason: str | None = Field(default=None, description="Reason code or message")
    operations: list[str] | None = Field(default=None, description="Available operations")

    # Additional data including HMAC signature
    additionalData: dict[str, Any] | None = Field(
        default=None,
        description="Additional data including hmacSignature",
    )

    model_config = {"populate_by_name": True}


class AdyenNotificationItemWrapper(BaseModel):
    """Wrapper for notification item (Adyen wraps items in this structure)."""

    NotificationRequestItem: AdyenNotificationItem


class AdyenNotificationRequest(BaseModel):
    """
    Adyen webhook notification request.

    Adyen sends batched notifications - multiple items can be in one request.
    """

    live: bool = Field(..., description="True if production, false if test")
    notificationItems: list[AdyenNotificationItemWrapper] = Field(
        ...,
        description="List of notification items",
    )

    @property
    def items(self) -> list[AdyenNotificationItem]:
        """Extract notification items from wrappers."""
        return [wrapper.NotificationRequestItem for wrapper in self.notificationItems]


# Supported Adyen event codes
ADYEN_EVENT_CODES = Literal[
    "AUTHORISATION",
    "AUTHORISATION_ADJUSTMENT",
    "CANCELLATION",
    "CANCEL_OR_REFUND",
    "CAPTURE",
    "CAPTURE_FAILED",
    "CHARGEBACK",
    "CHARGEBACK_REVERSED",
    "HANDLED_EXTERNALLY",
    "ORDER_OPENED",
    "ORDER_CLOSED",
    "PENDING",
    "PROCESS_RETRY",
    "REFUND",
    "REFUND_FAILED",
    "REFUNDED_REVERSED",
    "REPORT_AVAILABLE",
    "REQUEST_FOR_INFORMATION",
    "SECOND_CHARGEBACK",
    "VOID_PENDING_REFUND",
]
