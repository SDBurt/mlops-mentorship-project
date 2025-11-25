# temporal/activities/fraud_check.py
from temporalio import activity
from dataclasses import dataclass
import random

@dataclass
class FraudCheckResult:
    is_safe: bool
    risk_score: float
    reasons: list[str]

@activity.defn
async def check_fraud(payment_data: dict) -> FraudCheckResult:
    """
    Simulates fraud detection. In production, this would call
    an ML inference endpoint.
    """
    activity.logger.info(f"Checking fraud for {payment_data.get('transaction_id')}")

    # Simulate ML model inference
    risk_score = random.random()

    reasons = []
    if payment_data.get("amount", 0) > 100000:  # > $1000
        risk_score += 0.3
        reasons.append("high_amount")

    if payment_data.get("currency") not in ["usd", "cad", "gbp", "eur"]:
        risk_score += 0.2
        reasons.append("unusual_currency")

    return FraudCheckResult(
        is_safe=risk_score < 0.95,
        risk_score=min(risk_score, 1.0),
        reasons=reasons
    )
