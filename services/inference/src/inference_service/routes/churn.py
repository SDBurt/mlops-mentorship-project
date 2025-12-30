"""Churn prediction endpoint."""

import asyncio
import logging
import random
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class ChurnPredictionRequest(BaseModel):
    """Request payload for churn prediction."""

    customer_id: str = Field(..., description="Customer identifier")
    merchant_id: str | None = Field(default=None, description="Merchant identifier")

    # Payment history signals (used as fallback or additional context)
    total_payments: int = Field(default=0, ge=0, description="Total payment attempts")
    successful_payments: int = Field(default=0, ge=0, description="Successful payments")
    failed_payments: int = Field(default=0, ge=0, description="Failed payment attempts")
    recovered_payments: int = Field(default=0, ge=0, description="Recovered failed payments")

    # Recent activity
    days_since_last_payment: int = Field(default=0, ge=0, description="Days since last payment")
    days_since_last_failure: int | None = Field(default=None, description="Days since last failure")
    consecutive_failures: int = Field(default=0, ge=0, description="Consecutive failed payments")


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


def compute_churn_probability_mock(request: ChurnPredictionRequest) -> tuple[float, list[str], list[str]]:
    """
    Compute mock churn probability based on payment signals.
    """
    risk_factors = []
    recommended_actions = []
    base_score = 0.05

    if request.consecutive_failures >= 3:
        base_score += 0.35
        risk_factors.append("multiple_consecutive_failures")
        recommended_actions.append("immediate_customer_outreach")
    elif request.consecutive_failures >= 1:
        base_score += 0.15
        risk_factors.append("recent_failure")
        recommended_actions.append("send_payment_update_reminder")

    if request.days_since_last_payment > 30:
        base_score += 0.15
        risk_factors.append("payment_gap")
        recommended_actions.append("engagement_campaign")

    noise = (hash(request.customer_id) % 1000 / 10000) - 0.05
    final_score = max(0.0, min(1.0, base_score + noise))

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


@router.post("/predict", response_model=ChurnPredictionResponse)
async def predict_churn(request: ChurnPredictionRequest) -> ChurnPredictionResponse:
    """
    Predict churn probability for a customer.

    Tries to use Feast for real-time features and MLflow for the model.
    Falls back to mock logic if MLOps components are unavailable.
    """
    from ..main import get_model, feature_store

    logger.info(f"Predicting churn for customer: {request.customer_id}")

    model = get_model("churn-prediction")
    churn_probability = None
    risk_factors = []
    recommended_actions = []
    model_version = settings.model_version

    if model and feature_store:
        try:
            # 1. Fetch features from Feast online store
            entity_rows = [{"customer_id": request.customer_id}]
            features = [
                "customer_payment_features:total_payments_30d",
                "customer_payment_features:total_payments_90d",
                "customer_payment_features:failure_rate_30d",
                "customer_payment_features:consecutive_failures",
                "customer_payment_features:recovery_rate_30d",
                "customer_payment_features:days_since_last_payment",
                "customer_payment_features:payment_method_count",
            ]

            feature_vector = feature_store.get_online_features(
                features=features,
                entity_rows=entity_rows
            ).to_df()

            # 2. Prepare features for model
            X = pd.DataFrame([{
                "total_payments_30d": feature_vector["total_payments_30d"].iloc[0],
                "total_payments_90d": feature_vector["total_payments_90d"].iloc[0],
                "failure_rate_30d": feature_vector["failure_rate_30d"].iloc[0],
                "consecutive_failures": feature_vector["consecutive_failures"].iloc[0],
                "recovery_rate_30d": feature_vector["recovery_rate_30d"].iloc[0],
                "days_since_last_payment": feature_vector["days_since_last_payment"].iloc[0],
                "payment_method_count": feature_vector["payment_method_count"].iloc[0],
            }]).fillna(0)

            # 3. Predict using MLflow model
            churn_probability = float(model.predict_proba(X)[0, 1])
            model_version = "v1-feast"

            # Add dynamic risk factors based on features
            if X["consecutive_failures"].iloc[0] >= 2:
                risk_factors.append("multiple_consecutive_failures")
                recommended_actions.append("immediate_customer_outreach")
            if X["failure_rate_30d"].iloc[0] > 0.3:
                risk_factors.append("high_recent_failure_rate")
                recommended_actions.append("review_payment_methods")

        except Exception as e:
            logger.warning(f"Error using MLOps for {request.customer_id}: {e}. Falling back to mock.")

    if churn_probability is None:
        # Fallback to mock
        churn_probability, risk_factors, recommended_actions = compute_churn_probability_mock(request)
        model_version = "mock-v1"

    risk_level = get_risk_level(churn_probability)

    return ChurnPredictionResponse(
        customer_id=request.customer_id,
        churn_probability=churn_probability,
        risk_level=risk_level,
        risk_factors=risk_factors,
        recommended_actions=recommended_actions,
        model_version=model_version,
    )
