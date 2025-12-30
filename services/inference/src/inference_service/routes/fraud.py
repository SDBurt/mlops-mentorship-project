"""Fraud scoring endpoint."""

import asyncio
import logging
import random

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..config import settings
# We'll import these inside the route to avoid circular imports
# or use a dependency injection pattern if this were larger

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
SUSPICIOUS_CARD_BRANDS = {"unknown", "other"}


def compute_fraud_score_mock(request: FraudScoreRequest) -> tuple[float, list[str]]:
    """
    Compute mock fraud score based on payment attributes.
    """
    risk_factors = []
    base_score = 0.05

    if request.amount_cents > 100_000:
        base_score += 0.25
        risk_factors.append("very_high_amount")
    elif request.amount_cents > 50_000:
        base_score += 0.15
        risk_factors.append("high_amount")

    if not request.customer_id:
        base_score += 0.15
        risk_factors.append("guest_checkout")

    if request.card_brand and request.card_brand.lower() in SUSPICIOUS_CARD_BRANDS:
        base_score += 0.10
        risk_factors.append("unknown_card_brand")

    noise = ((hash(request.event_id) % 1001) / 1000 - 0.5) * 0.1
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

    Tries to use Feast for real-time features and MLflow for the model.
    Falls back to mock logic if MLOps components are unavailable.
    """
    from ..main import get_model, feature_store

    logger.info(f"Scoring fraud for event: {request.event_id}")

    model = get_model("fraud-detection")
    fraud_score = None
    risk_factors = []
    model_version = settings.model_version

    if model and feature_store and request.customer_id:
        try:
            # 1. Fetch features from Feast online store
            entity_rows = [{"customer_id": request.customer_id}]
            features = [
                "customer_payment_features:total_payments_30d",
                "customer_payment_features:failure_rate_30d",
                "customer_payment_features:fraud_score_avg",
                "customer_payment_features:high_risk_payment_count",
            ]

            if request.merchant_id:
                entity_rows[0]["merchant_id"] = request.merchant_id
                features.extend([
                    "merchant_payment_features:fraud_rate_30d",
                    "merchant_payment_features:high_risk_transaction_pct",
                    "merchant_payment_features:merchant_health_score",
                ])

            feature_vector = feature_store.get_online_features(
                features=features,
                entity_rows=entity_rows
            ).to_df()

            # 2. Prepare features for model (matching training columns)
            X = pd.DataFrame([{
                "fraud_score_avg": feature_vector["fraud_score_avg"].iloc[0],
                "failure_rate_30d": feature_vector["failure_rate_30d"].iloc[0],
                "total_payments_30d": feature_vector["total_payments_30d"].iloc[0],
                "high_risk_payment_count": feature_vector["high_risk_payment_count"].iloc[0],
                "merchant_fraud_rate": feature_vector.get("fraud_rate_30d", [0]).iloc[0],
                "high_risk_transaction_pct": feature_vector.get("high_risk_transaction_pct", [0]).iloc[0],
                "merchant_health_score": feature_vector.get("merchant_health_score", [0]).iloc[0],
            }]).fillna(0)

            # 3. Predict using MLflow model
            fraud_score = float(model.predict_proba(X)[0, 1])
            model_version = "v1-feast"
            logger.info(f"Model prediction for {request.event_id}: {fraud_score}")

        except Exception as e:
            logger.warning(f"Error using MLOps for {request.event_id}: {e}. Falling back to mock.")

    if fraud_score is None:
        # Fallback to mock
        fraud_score, risk_factors = compute_fraud_score_mock(request)
        model_version = "mock-v1"

    risk_level = get_risk_level(fraud_score)

    return FraudScoreResponse(
        event_id=request.event_id,
        fraud_score=fraud_score,
        risk_level=risk_level,
        risk_factors=risk_factors,
        model_version=model_version,
    )
