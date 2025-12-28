"""
Inference service request and response models.

This module defines the API contract between:
- Orchestrator (produces requests)
- Inference Service (handles requests)
- Temporal workflows (orchestrates)
"""

from datetime import datetime, timezone
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


class ChurnPredictionRequest(BaseModel):
    """Request payload for churn prediction."""

    customer_id: str = Field(..., description="Customer identifier")
    merchant_id: str | None = Field(default=None, description="Merchant identifier")

    # Payment history signals
    total_payments: int = Field(default=0, ge=0, description="Total payment attempts")
    successful_payments: int = Field(default=0, ge=0, description="Successful payments")
    failed_payments: int = Field(default=0, ge=0, description="Failed payment attempts")
    recovered_payments: int = Field(default=0, ge=0, description="Recovered failed payments")

    # Recent activity
    days_since_last_payment: int = Field(default=0, ge=0, description="Days since last payment")
    days_since_last_failure: int | None = Field(default=None, description="Days since last failure")
    consecutive_failures: int = Field(default=0, ge=0, description="Consecutive failed payments")


class ChurnPredictionResponse(BaseModel):
    """Response payload from churn prediction."""

    customer_id: str
    churn_probability: float = Field(..., ge=0.0, le=1.0)
    risk_level: str
    risk_factors: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    days_to_churn_estimate: int | None = Field(
        default=None,
        description="Estimated days until churn if no intervention"
    )
    model_version: str = Field(default="mock-v1")
    predicted_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
