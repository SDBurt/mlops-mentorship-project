"""Fraud scoring endpoint."""

import asyncio
import logging
import random

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class FraudScoreRequest(BaseModel):
    """Request payload for fraud scoring."""

    event_id: str = Field(..., description="Payment event ID")
    amount_cents: int = Field(..., ge=0, description="Payment amount in cents")
    currency: str = Field(..., description="ISO 4217 currency code")
    customer_id: str | None = Field(default=None, description="Customer identifier")
    merchant_id: str | None = Field(default=None, description="Merchant identifier")
    payment_method_type: str | None = Field(default=None, description="Payment method type")
    card_brand: str | None = Field(default=None, description="Card brand")


class FraudScoreResponse(BaseModel):
    """Response payload from fraud scoring."""

    event_id: str
    fraud_score: float = Field(..., ge=0.0, le=1.0)
    risk_level: str
    risk_factors: list[str] = Field(default_factory=list)
    model_version: str = Field(default="mock-v1")


# Risk thresholds
HIGH_RISK_THRESHOLD = 0.7
MEDIUM_RISK_THRESHOLD = 0.3

# High-risk patterns
HIGH_RISK_CURRENCIES = {"RUB", "UAH", "BYN"}
SUSPICIOUS_CARD_BRANDS = {"unknown", "other"}


def compute_fraud_score(request: FraudScoreRequest) -> tuple[float, list[str]]:
    """
    Compute mock fraud score based on payment attributes.

    This is a deterministic mock implementation for demonstration purposes.
    Real implementations would use ML models.
    """
    risk_factors = []
    base_score = 0.05  # Start with low base risk

    # Factor 1: Transaction amount
    if request.amount_cents > 100_000_00:  # > $1000
        base_score += 0.25
        risk_factors.append("very_high_amount")
    elif request.amount_cents > 50_000_00:  # > $500
        base_score += 0.15
        risk_factors.append("high_amount")
    elif request.amount_cents > 10_000_00:  # > $100
        base_score += 0.05
        risk_factors.append("moderate_amount")

    # Factor 2: Missing customer ID (guest checkout)
    if not request.customer_id:
        base_score += 0.15
        risk_factors.append("guest_checkout")

    # Factor 3: High-risk currencies
    if request.currency and request.currency.upper() in HIGH_RISK_CURRENCIES:
        base_score += 0.20
        risk_factors.append("high_risk_currency")

    # Factor 4: Suspicious card brand
    if request.card_brand and request.card_brand.lower() in SUSPICIOUS_CARD_BRANDS:
        base_score += 0.10
        risk_factors.append("unknown_card_brand")

    # Factor 5: Non-card payment methods have slightly higher risk
    if request.payment_method_type and request.payment_method_type not in ["card", "credit_card"]:
        base_score += 0.05
        risk_factors.append("alternative_payment_method")

    # Add small random noise for realism (deterministic based on event_id hash)
    noise_seed = hash(request.event_id) % 1000 / 10000  # -0.05 to 0.05
    noise = (noise_seed - 0.05)
    final_score = max(0.0, min(1.0, base_score + noise))

    return round(final_score, 4), risk_factors


def get_risk_level(score: float) -> str:
    """Determine risk level from score."""
    if score >= HIGH_RISK_THRESHOLD:
        return "high"
    elif score >= MEDIUM_RISK_THRESHOLD:
        return "medium"
    return "low"


@router.post("/score", response_model=FraudScoreResponse)
async def get_fraud_score(request: FraudScoreRequest) -> FraudScoreResponse:
    """
    Get fraud score for a payment event.

    This is a mock implementation that uses rule-based scoring for demonstration.
    """
    logger.info(f"Scoring fraud for event: {request.event_id}")

    # Simulate processing latency
    latency = random.randint(settings.min_latency_ms, settings.max_latency_ms) / 1000
    await asyncio.sleep(latency)

    fraud_score, risk_factors = compute_fraud_score(request)
    risk_level = get_risk_level(fraud_score)

    logger.info(
        f"Fraud score for {request.event_id}: {fraud_score} ({risk_level}), "
        f"factors: {risk_factors}"
    )

    return FraudScoreResponse(
        event_id=request.event_id,
        fraud_score=fraud_score,
        risk_level=risk_level,
        risk_factors=risk_factors,
        model_version=settings.model_version,
    )
