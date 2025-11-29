"""Churn prediction endpoint."""

import asyncio
import logging
import random
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


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

    # Subscription info
    subscription_age_days: int = Field(default=0, ge=0, description="Days since subscription start")
    payment_method_age_days: int = Field(default=0, ge=0, description="Days since payment method added")
    has_backup_payment_method: bool = Field(default=False, description="Has backup payment method")


class ChurnRiskLevel(str):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


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


def compute_churn_probability(request: ChurnPredictionRequest) -> tuple[float, list[str], list[str]]:
    """
    Compute mock churn probability based on payment signals.

    This is a deterministic mock implementation for demonstration.
    Real implementations would use ML models trained on historical churn data.

    Returns:
        Tuple of (probability, risk_factors, recommended_actions)
    """
    risk_factors = []
    recommended_actions = []
    base_score = 0.05  # Start with low base churn risk

    # Factor 1: Payment failure rate
    if request.total_payments > 0:
        failure_rate = request.failed_payments / request.total_payments
        if failure_rate > 0.3:
            base_score += 0.25
            risk_factors.append("high_failure_rate")
            recommended_actions.append("review_payment_method")
        elif failure_rate > 0.15:
            base_score += 0.15
            risk_factors.append("elevated_failure_rate")
            recommended_actions.append("proactive_payment_method_update")

    # Factor 2: Consecutive failures (strongest signal)
    if request.consecutive_failures >= 3:
        base_score += 0.35
        risk_factors.append("multiple_consecutive_failures")
        recommended_actions.append("immediate_customer_outreach")
    elif request.consecutive_failures >= 2:
        base_score += 0.20
        risk_factors.append("consecutive_failures")
        recommended_actions.append("send_payment_update_reminder")
    elif request.consecutive_failures == 1:
        base_score += 0.10
        risk_factors.append("recent_failure")

    # Factor 3: Days since last successful payment
    if request.days_since_last_payment > 45:
        base_score += 0.20
        risk_factors.append("long_payment_gap")
        recommended_actions.append("engagement_campaign")
    elif request.days_since_last_payment > 30:
        base_score += 0.10
        risk_factors.append("payment_gap")

    # Factor 4: Payment method age (old cards more likely to expire)
    if request.payment_method_age_days > 365:
        base_score += 0.15
        risk_factors.append("aging_payment_method")
        recommended_actions.append("proactive_card_update")
    elif request.payment_method_age_days > 270:
        base_score += 0.08
        risk_factors.append("payment_method_approaching_expiry")

    # Factor 5: No backup payment method
    if not request.has_backup_payment_method:
        base_score += 0.10
        risk_factors.append("no_backup_payment_method")
        recommended_actions.append("request_backup_payment_method")

    # Factor 6: New subscription (higher churn in first 90 days)
    if request.subscription_age_days < 30:
        base_score += 0.15
        risk_factors.append("new_subscription")
        recommended_actions.append("onboarding_support")
    elif request.subscription_age_days < 90:
        base_score += 0.08
        risk_factors.append("early_subscription_period")

    # Protective factor: Good recovery rate
    if request.failed_payments > 0 and request.recovered_payments > 0:
        recovery_rate = request.recovered_payments / request.failed_payments
        if recovery_rate > 0.8:
            base_score -= 0.10
        elif recovery_rate > 0.5:
            base_score -= 0.05

    # Protective factor: Long tenure with good history
    if request.subscription_age_days > 365 and request.consecutive_failures == 0:
        base_score -= 0.10

    # Add small noise for realism (deterministic based on customer_id hash)
    noise_seed = hash(request.customer_id) % 1000 / 10000
    noise = (noise_seed - 0.05)
    final_score = max(0.0, min(1.0, base_score + noise))

    # Deduplicate recommendations
    recommended_actions = list(dict.fromkeys(recommended_actions))

    return round(final_score, 4), risk_factors, recommended_actions


def get_risk_level(probability: float) -> str:
    """Determine risk level from churn probability."""
    if probability >= 0.75:
        return "critical"
    elif probability >= 0.5:
        return "high"
    elif probability >= 0.25:
        return "medium"
    return "low"


def estimate_days_to_churn(probability: float, consecutive_failures: int) -> int | None:
    """Estimate days until churn based on probability and failure pattern."""
    if probability < 0.25:
        return None  # Low risk, not imminent

    # Higher probability = sooner churn
    base_days = int((1 - probability) * 60)  # 0-60 days scale

    # Consecutive failures accelerate churn
    if consecutive_failures >= 3:
        base_days = max(1, base_days // 3)
    elif consecutive_failures >= 2:
        base_days = max(3, base_days // 2)

    return base_days


@router.post("/predict", response_model=ChurnPredictionResponse)
async def predict_churn(request: ChurnPredictionRequest) -> ChurnPredictionResponse:
    """
    Predict churn probability for a customer.

    This endpoint analyzes payment history signals to predict the likelihood
    that a customer will churn due to payment failures (involuntary churn).
    """
    logger.info(f"Predicting churn for customer: {request.customer_id}")

    # Simulate processing latency
    latency = random.randint(settings.min_latency_ms, settings.max_latency_ms) / 1000
    await asyncio.sleep(latency)

    churn_probability, risk_factors, recommended_actions = compute_churn_probability(request)
    risk_level = get_risk_level(churn_probability)
    days_to_churn = estimate_days_to_churn(churn_probability, request.consecutive_failures)

    logger.info(
        f"Churn prediction for {request.customer_id}: {churn_probability:.2%} ({risk_level}), "
        f"factors: {risk_factors}"
    )

    return ChurnPredictionResponse(
        customer_id=request.customer_id,
        churn_probability=churn_probability,
        risk_level=risk_level,
        risk_factors=risk_factors,
        recommended_actions=recommended_actions,
        days_to_churn_estimate=days_to_churn,
        model_version=settings.model_version,
    )
