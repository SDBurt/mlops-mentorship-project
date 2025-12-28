"""Square webhook Pydantic models matching the real Square API structure."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Nested Data Objects
# =============================================================================


class SquareMoney(BaseModel):
    """Square money object representing an amount with currency."""

    amount: int = Field(..., ge=0, description="Amount in smallest currency unit")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO 4217 currency code")

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()


class SquareCardDetails(BaseModel):
    """Square card payment details."""

    card_brand: str | None = Field(default=None, alias="card_brand")
    last_4: str | None = Field(default=None, alias="last_4")
    exp_month: int | None = Field(default=None, ge=1, le=12)
    exp_year: int | None = Field(default=None, ge=2020)
    fingerprint: str | None = None
    card_type: str | None = None
    prepaid_type: str | None = None
    bin: str | None = None

    model_config = {"populate_by_name": True}


class SquarePaymentData(BaseModel):
    """Square payment object."""

    id: str = Field(..., description="Payment ID")
    created_at: str = Field(..., description="ISO 8601 timestamp")
    updated_at: str | None = None
    amount_money: SquareMoney
    tip_money: SquareMoney | None = None
    total_money: SquareMoney | None = None
    app_fee_money: SquareMoney | None = None
    status: Literal["APPROVED", "COMPLETED", "CANCELED", "FAILED", "PENDING"]
    source_type: str | None = Field(default=None, description="Payment source type (CARD, CASH, etc.)")
    card_details: SquareCardDetails | None = None
    location_id: str = Field(..., description="Square location ID")
    order_id: str | None = None
    customer_id: str | None = None
    reference_id: str | None = None
    note: str | None = None
    buyer_email_address: str | None = None

    # Failure info
    delay_action: str | None = None
    delay_duration: str | None = None

    model_config = {"populate_by_name": True}


class SquareRefundData(BaseModel):
    """Square refund object."""

    id: str = Field(..., description="Refund ID")
    created_at: str = Field(..., description="ISO 8601 timestamp")
    updated_at: str | None = None
    amount_money: SquareMoney
    status: Literal["PENDING", "COMPLETED", "REJECTED", "FAILED"]
    payment_id: str = Field(..., description="Associated payment ID")
    order_id: str | None = None
    location_id: str
    reason: str | None = None

    model_config = {"populate_by_name": True}


# =============================================================================
# Event Data Wrapper
# =============================================================================


class SquareEventData(BaseModel):
    """Square event data wrapper containing the event object."""

    type: str = Field(..., description="Object type (payment, refund, etc.)")
    id: str = Field(..., description="Object ID")
    object: dict[str, Any] = Field(..., description="The actual event object")


# =============================================================================
# Main Event Model
# =============================================================================


class SquareWebhookEvent(BaseModel):
    """Square webhook event envelope."""

    merchant_id: str = Field(..., description="Square merchant ID")
    type: str = Field(..., description="Event type (e.g., payment.created)")
    event_id: str = Field(..., description="Unique event ID")
    created_at: str = Field(..., description="ISO 8601 timestamp")
    data: SquareEventData = Field(..., description="Event data wrapper")

    @property
    def event_category(self) -> str:
        """Return the event category for Kafka topic routing."""
        # Extract category from type like "payment.created" -> "payment"
        return self.type.split(".")[0]

    @property
    def payment_data(self) -> SquarePaymentData | None:
        """Extract and parse payment data if this is a payment event."""
        if self.event_category == "payment":
            payment_dict = self.data.object.get("payment")
            if payment_dict:
                return SquarePaymentData.model_validate(payment_dict)
        return None

    @property
    def refund_data(self) -> SquareRefundData | None:
        """Extract and parse refund data if this is a refund event."""
        if self.event_category == "refund":
            refund_dict = self.data.object.get("refund")
            if refund_dict:
                return SquareRefundData.model_validate(refund_dict)
        return None
