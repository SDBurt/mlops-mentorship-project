# temporal/activities/fraud_check.py
"""
Fraud detection activity.

Evaluates payment risk using normalized fraud signals from any provider.
In production, this would call an ML inference endpoint (e.g., Stripe Radar, Kount).
"""
from temporalio import activity
from dataclasses import dataclass
import random


@dataclass
class FraudCheckResult:
    is_safe: bool
    risk_score: float
    risk_level: str  # "normal", "elevated", "high"
    reasons: list[str]


@activity.defn
async def check_fraud(payment_data: dict) -> FraudCheckResult:
    """
    Simulates fraud detection using provider-agnostic normalized signals.

    Works with NormalizedPayment schema:
    - amount_cents: Transaction amount in cents
    - currency: ISO 4217 currency code
    - card_funding: "credit", "debit", "prepaid", "unknown"
    - fraud_signals: {cvc_check, avs_check, postal_check, risk_level}
    - provider: Source provider for logging
    """
    # Get payment identifier (works with normalized schema)
    payment_id = payment_data.get(
        'provider_payment_id',
        payment_data.get('id', payment_data.get('transaction_id', 'unknown'))
    )
    provider = payment_data.get('provider', 'unknown')
    activity.logger.info(f"Checking fraud for {payment_id} from {provider}")

    # Base risk score from "ML model"
    risk_score = random.random() * 0.5  # Start with 0-0.5 base

    reasons = []

    # Amount-based risk (high amounts are riskier)
    # Support both normalized (amount_cents) and legacy (amount) fields
    amount = payment_data.get("amount_cents", payment_data.get("amount", 0))
    if amount > 50000:  # > $500
        risk_score += 0.15
        reasons.append("high_amount")
    if amount > 100000:  # > $1000
        risk_score += 0.2
        reasons.append("very_high_amount")

    # Currency risk (non-standard currencies slightly riskier)
    currency = payment_data.get("currency", "USD").upper()
    if currency not in ["USD", "CAD", "GBP", "EUR", "AUD"]:
        risk_score += 0.15
        reasons.append("unusual_currency")

    # Get fraud signals (normalized format)
    fraud_signals = payment_data.get("fraud_signals", {})

    # CVC check
    cvc_check = fraud_signals.get("cvc_check", "unknown")
    if cvc_check == "fail":
        risk_score += 0.3
        reasons.append("cvc_check_failed")

    # AVS (Address Verification) check
    avs_check = fraud_signals.get("avs_check", "unknown")
    if avs_check == "fail":
        risk_score += 0.15
        reasons.append("address_mismatch")

    # Postal code check
    postal_check = fraud_signals.get("postal_check", "unknown")
    if postal_check == "fail":
        risk_score += 0.2
        reasons.append("postal_code_mismatch")

    # Provider-supplied risk level (if available)
    provider_risk = fraud_signals.get("risk_level", "unknown")
    if provider_risk == "high":
        risk_score += 0.25
        reasons.append("provider_flagged_high_risk")
    elif provider_risk == "medium":
        risk_score += 0.1
        reasons.append("provider_flagged_medium_risk")

    # Card type risk - support both normalized and legacy formats
    card_funding = payment_data.get("card_funding")
    if not card_funding:
        # Legacy format fallback
        card_funding = (
            payment_data
            .get("payment_method_details", {})
            .get("card", {})
            .get("funding")
        )
    if card_funding == "prepaid":
        risk_score += 0.25
        reasons.append("prepaid_card")

    # Velocity check simulation (random for demo)
    if random.random() < 0.05:  # 5% chance of velocity flag
        risk_score += 0.3
        reasons.append("velocity_limit_exceeded")

    # Determine risk level
    risk_score = min(risk_score, 1.0)
    if risk_score < 0.3:
        risk_level = "normal"
    elif risk_score < 0.7:
        risk_level = "elevated"
    else:
        risk_level = "high"

    # Block if risk is too high (95% threshold)
    is_safe = risk_score < 0.95

    activity.logger.info(
        f"Fraud check for {payment_id} [{provider}]: "
        f"score={risk_score:.2f}, level={risk_level}, safe={is_safe}"
    )

    return FraudCheckResult(
        is_safe=is_safe,
        risk_score=round(risk_score, 3),
        risk_level=risk_level,
        reasons=reasons
    )
