# temporal/activities/enrich_context.py
"""
Payment context enrichment activity.

Gathers additional context about the payment for ML-driven retry prediction.
In production, this would query customer databases, payment history, etc.
For this demo, we simulate realistic feature generation.
"""
import random
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any

from temporalio import activity

from temporal.activities.normalize_event import NormalizedFailedPayment


@dataclass
class EnrichedPaymentContext:
    """
    Enriched payment data with ML features for retry prediction.

    Contains both the normalized payment and computed features that
    help the ML model predict optimal retry timing and method.
    """
    # Original normalized payment
    payment: dict  # NormalizedFailedPayment as dict

    # Customer features
    customer_lifetime_value: float  # Total revenue from customer
    customer_tenure_days: int  # Days since first payment
    customer_payment_count: int  # Total payments from customer
    customer_failure_rate: float  # Historical failure rate (0.0-1.0)

    # Card features
    card_age_days: int  # Days since card was first used
    card_success_rate: float  # Historical success rate for this card
    card_is_primary: bool  # Is this the customer's primary card?

    # Payment history features
    previous_failures_30d: int  # Failed payments in last 30 days
    previous_retries: int  # Prior retry attempts for this payment
    days_since_last_success: int  # Days since last successful payment
    avg_days_between_payments: float  # Average payment frequency

    # Merchant features
    merchant_category_risk: str  # "low", "medium", "high"
    merchant_retry_success_rate: float  # Historical retry success for this merchant

    # Temporal features
    is_weekend: bool
    hour_of_day: int
    day_of_month: int
    is_end_of_month: bool  # Last 3 days of month

    # Derived features
    is_first_retry: bool
    is_subscription: bool  # Based on merchant category
    amount_percentile: float  # Where this amount falls vs historical

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for workflow."""
        return asdict(self)


# Merchant categories with higher risk of payment failures
HIGH_RISK_CATEGORIES = {
    "crypto", "gambling", "adult", "digital_goods", "subscription",
}

MEDIUM_RISK_CATEGORIES = {
    "streaming", "saas", "software", "cloud_infrastructure", "cloud_platform",
}

SUBSCRIPTION_CATEGORIES = {
    "streaming", "saas", "software", "subscription", "cloud_platform",
    "cloud_infrastructure", "developer_tools",
}


def _simulate_customer_features(payment: NormalizedFailedPayment) -> dict:
    """
    Simulate customer-level features.

    In production, this would query a customer database or feature store.
    """
    # Use customer_id hash for deterministic but varied results
    seed = hash(payment.customer_id) % 10000
    random.seed(seed)

    # Higher-value customers tend to have more history
    base_ltv = payment.amount_cents * random.uniform(10, 100)

    return {
        "customer_lifetime_value": round(base_ltv / 100, 2),  # Convert to dollars
        "customer_tenure_days": random.randint(30, 1500),
        "customer_payment_count": random.randint(1, 200),
        "customer_failure_rate": round(random.uniform(0.02, 0.15), 3),
    }


def _simulate_card_features(payment: NormalizedFailedPayment) -> dict:
    """
    Simulate card-level features.

    In production, this would query card history and token vault.
    """
    seed = hash(f"{payment.customer_id}:{payment.card_last4}") % 10000
    random.seed(seed)

    # Prepaid cards have lower success rates
    base_success = 0.92 if payment.card_funding != "prepaid" else 0.75

    return {
        "card_age_days": random.randint(1, 730),
        "card_success_rate": round(base_success + random.uniform(-0.1, 0.05), 3),
        "card_is_primary": random.random() > 0.2,  # 80% primary
    }


def _simulate_payment_history(payment: NormalizedFailedPayment) -> dict:
    """
    Simulate payment history features.

    In production, this would aggregate from payment history tables.
    """
    seed = hash(f"{payment.customer_id}:{payment.failure_timestamp}") % 10000
    random.seed(seed)

    return {
        "previous_failures_30d": random.randint(0, 5),
        "previous_retries": payment.retry_count,
        "days_since_last_success": random.randint(1, 60),
        "avg_days_between_payments": round(random.uniform(7, 45), 1),
    }


def _compute_merchant_risk(merchant_category: str) -> str:
    """Determine merchant category risk level."""
    category_lower = merchant_category.lower()

    if category_lower in HIGH_RISK_CATEGORIES:
        return "high"
    elif category_lower in MEDIUM_RISK_CATEGORIES:
        return "medium"
    else:
        return "low"


def _simulate_merchant_features(payment: NormalizedFailedPayment) -> dict:
    """
    Simulate merchant-level features.

    In production, this would aggregate merchant-level retry statistics.
    """
    risk = _compute_merchant_risk(payment.merchant_category)

    # Success rates vary by merchant risk
    base_success = {
        "low": 0.70,
        "medium": 0.55,
        "high": 0.40,
    }.get(risk, 0.50)

    return {
        "merchant_category_risk": risk,
        "merchant_retry_success_rate": round(base_success + random.uniform(-0.1, 0.1), 3),
    }


def _compute_temporal_features() -> dict:
    """Compute time-based features."""
    now = datetime.utcnow()

    return {
        "is_weekend": now.weekday() >= 5,
        "hour_of_day": now.hour,
        "day_of_month": now.day,
        "is_end_of_month": now.day >= 28,
    }


def _compute_derived_features(
    payment: NormalizedFailedPayment,
    customer_features: dict,
) -> dict:
    """Compute derived features from other features."""
    # Determine if subscription based on merchant category
    is_subscription = payment.merchant_category.lower() in SUBSCRIPTION_CATEGORIES

    # Amount percentile (simplified - in production, use historical distribution)
    amount_percentile = min(payment.amount_cents / 50000, 1.0)  # Normalize to 0-1

    return {
        "is_first_retry": payment.retry_count == 0,
        "is_subscription": is_subscription,
        "amount_percentile": round(amount_percentile, 3),
    }


@activity.defn
async def enrich_payment_context(
    normalized_payment: NormalizedFailedPayment | dict,
) -> EnrichedPaymentContext:
    """
    Enrich a normalized payment with ML features.

    This activity gathers additional context about the payment that helps
    the ML model predict the optimal retry strategy.

    Args:
        normalized_payment: Normalized payment from normalize_event activity

    Returns:
        EnrichedPaymentContext with ML features
    """
    activity.logger.info("Enriching payment context")

    # Handle both dataclass and dict inputs
    if isinstance(normalized_payment, dict):
        # Reconstruct dataclass from dict
        payment = NormalizedFailedPayment(**normalized_payment)
    else:
        payment = normalized_payment

    # Gather features
    customer_features = _simulate_customer_features(payment)
    card_features = _simulate_card_features(payment)
    payment_history = _simulate_payment_history(payment)
    merchant_features = _simulate_merchant_features(payment)
    temporal_features = _compute_temporal_features()
    derived_features = _compute_derived_features(payment, customer_features)

    enriched = EnrichedPaymentContext(
        payment=payment.to_dict() if hasattr(payment, 'to_dict') else payment,
        **customer_features,
        **card_features,
        **payment_history,
        **merchant_features,
        **temporal_features,
        **derived_features,
    )

    activity.logger.info(
        f"Enriched context: LTV=${enriched.customer_lifetime_value:.2f}, "
        f"card_success_rate={enriched.card_success_rate:.1%}, "
        f"merchant_risk={enriched.merchant_category_risk}"
    )

    return enriched
