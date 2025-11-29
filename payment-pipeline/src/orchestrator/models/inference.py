"""Data models for inference service requests and responses."""

from enum import Enum

from pydantic import BaseModel, Field


class FraudScoreRequest(BaseModel):
    """Request payload for fraud scoring endpoint."""

    event_id: str = Field(..., description="Payment event ID")
    amount_cents: int = Field(..., ge=0, description="Payment amount in cents")
    currency: str = Field(..., description="ISO 4217 currency code")
    customer_id: str | None = Field(default=None, description="Customer identifier")
    merchant_id: str | None = Field(default=None, description="Merchant identifier")
    payment_method_type: str | None = Field(default=None, description="Payment method type")
    card_brand: str | None = Field(default=None, description="Card brand")


class FraudScoreResponse(BaseModel):
    """Response payload from fraud scoring endpoint."""

    event_id: str = Field(..., description="Payment event ID")
    fraud_score: float = Field(..., ge=0.0, le=1.0, description="Fraud probability (0-1)")
    risk_level: str = Field(..., description="Risk level: low, medium, high")
    risk_factors: list[str] = Field(default_factory=list, description="Identified risk factors")
    model_version: str = Field(default="mock-v1", description="Model version used")


class RetryAction(str, Enum):
    """Recommended retry action for failed payments."""

    RETRY_NOW = "retry_now"
    RETRY_DELAYED = "retry_delayed"
    DO_NOT_RETRY = "do_not_retry"
    CONTACT_CUSTOMER = "contact_customer"


class RetryStrategyRequest(BaseModel):
    """Request payload for retry strategy endpoint."""

    event_id: str = Field(..., description="Payment event ID")
    failure_code: str | None = Field(default=None, description="Payment failure code")
    failure_message: str | None = Field(default=None, description="Payment failure message")
    amount_cents: int = Field(..., ge=0, description="Payment amount in cents")
    attempt_count: int = Field(default=1, ge=1, description="Number of retry attempts so far")


class RetryStrategyResponse(BaseModel):
    """Response payload from retry strategy endpoint."""

    event_id: str = Field(..., description="Payment event ID")
    action: RetryAction = Field(..., description="Recommended retry action")
    delay_seconds: int | None = Field(default=None, description="Delay before retry (if applicable)")
    max_attempts: int = Field(default=5, description="Maximum number of retry attempts")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in recommendation")
    reason: str = Field(..., description="Explanation for the recommendation")
