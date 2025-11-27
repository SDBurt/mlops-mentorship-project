# temporal/activities/predict_retry_strategy.py
"""
ML-driven retry strategy prediction activity.

Predicts the optimal retry timing and method based on enriched payment context.
In production, this would call an ML inference endpoint. For this demo,
we implement a sophisticated rules-based model that mimics ML behavior.
"""
from dataclasses import dataclass, asdict
from typing import Any

from temporalio import activity

from temporal.activities.enrich_context import EnrichedPaymentContext
from temporal.providers.base import FailureCode


@dataclass
class RetryPrediction:
    """
    ML model prediction for retry strategy.

    Contains the recommended retry timing, method, and confidence metrics.
    """
    should_retry: bool
    delay_hours: float  # Hours to wait before retry
    retry_method: str  # "same_card", "request_update", "dunning_email", "give_up"
    confidence: float  # Model confidence in prediction (0.0-1.0)
    model_version: str  # For tracking which model made the prediction

    # Explanation for logging/debugging
    reason: str
    factors: list[str]  # Key factors that influenced the decision

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for workflow."""
        return asdict(self)


# Model version for tracking
MODEL_VERSION = "rules-v1.0.0"

# Maximum retry attempts before giving up
MAX_RETRY_ATTEMPTS = 5

# Failure codes that are non-retryable
NON_RETRYABLE_FAILURES = {
    FailureCode.FRAUD_SUSPECTED,
    FailureCode.INVALID_ACCOUNT,
    FailureCode.CARD_NOT_SUPPORTED,
}

# Failure codes that require card update
CARD_UPDATE_FAILURES = {
    FailureCode.EXPIRED_CARD,
}


def _compute_base_delay(failure_code: str, attempt: int) -> float:
    """
    Compute base delay based on failure code and attempt number.

    Different failure types have different optimal retry windows.
    """
    # Insufficient funds - longer delays work better (payday cycles)
    if failure_code == FailureCode.INSUFFICIENT_FUNDS:
        base_delays = [24, 48, 72, 120, 168]  # 1, 2, 3, 5, 7 days
        return base_delays[min(attempt - 1, len(base_delays) - 1)]

    # Processing errors - short delays, might be temporary
    if failure_code == FailureCode.PROCESSING_ERROR:
        return 1 + (attempt * 2)  # 1, 3, 5, 7, 9 hours

    # CVC errors - short delay, might be user fixing it
    if failure_code == FailureCode.INCORRECT_CVC:
        return 2 + (attempt * 4)  # 2, 6, 10, 14, 18 hours

    # Generic decline - moderate delays
    return 12 + (attempt * 12)  # 12, 24, 36, 48, 60 hours


def _adjust_delay_for_context(
    base_delay: float,
    context: EnrichedPaymentContext,
    factors: list[str],
) -> float:
    """
    Adjust delay based on enriched context features.

    This simulates how an ML model would weigh various features.
    """
    delay = base_delay

    # High-value customers get faster retries
    if context.customer_lifetime_value > 1000:
        delay *= 0.8
        factors.append("high_ltv_customer")
    elif context.customer_lifetime_value > 500:
        delay *= 0.9
        factors.append("medium_ltv_customer")

    # Subscription payments get faster retries (churn risk)
    if context.is_subscription:
        delay *= 0.85
        factors.append("subscription_payment")

    # End of month - delay slightly (billing congestion)
    if context.is_end_of_month:
        delay *= 1.2
        factors.append("end_of_month")

    # Weekend - delay more (banks closed)
    if context.is_weekend:
        delay *= 1.3
        factors.append("weekend")

    # Customer has high failure rate - longer delays
    if context.customer_failure_rate > 0.1:
        delay *= 1.2
        factors.append("high_failure_rate_customer")

    # Card has low success rate - longer delays
    if context.card_success_rate < 0.8:
        delay *= 1.15
        factors.append("low_card_success_rate")

    # Recent failures - back off more aggressively
    if context.previous_failures_30d > 2:
        delay *= 1.25
        factors.append("multiple_recent_failures")

    # High-risk merchant category - longer delays
    if context.merchant_category_risk == "high":
        delay *= 1.2
        factors.append("high_risk_merchant")

    # Ensure minimum 1 hour, maximum 168 hours (1 week)
    return max(1.0, min(delay, 168.0))


def _compute_confidence(
    context: EnrichedPaymentContext,
    failure_code: str,
    attempt: int,
) -> float:
    """
    Compute model confidence in the prediction.

    Higher confidence when we have more data and clearer signals.
    """
    confidence = 0.7  # Base confidence

    # More customer history = higher confidence
    if context.customer_payment_count > 10:
        confidence += 0.1
    if context.customer_tenure_days > 180:
        confidence += 0.05

    # Clear failure code = higher confidence
    if failure_code in {FailureCode.INSUFFICIENT_FUNDS, FailureCode.EXPIRED_CARD}:
        confidence += 0.1

    # Too many retries = lower confidence
    if attempt > 3:
        confidence -= 0.1

    # First retry = higher confidence
    if context.is_first_retry:
        confidence += 0.05

    return round(min(max(confidence, 0.3), 0.95), 3)


def _determine_retry_method(
    failure_code: str,
    context: EnrichedPaymentContext,
    attempt: int,
) -> tuple[str, str]:
    """
    Determine the retry method and reason.

    Returns:
        Tuple of (method, reason)
    """
    # Card expired - need customer action
    if failure_code in CARD_UPDATE_FAILURES:
        return "request_update", "Card has expired, customer update needed"

    # Fraud - don't retry
    if failure_code in NON_RETRYABLE_FAILURES:
        return "give_up", f"Non-retryable failure: {failure_code}"

    # Too many attempts
    if attempt >= MAX_RETRY_ATTEMPTS:
        return "give_up", f"Maximum retry attempts ({MAX_RETRY_ATTEMPTS}) exceeded"

    # High failure rate customer - consider dunning email after 2nd attempt
    if attempt > 2 and context.customer_failure_rate > 0.1:
        return "dunning_email", "Multiple failures, sending dunning email"

    # Not primary card and failed multiple times - request update
    if attempt > 2 and not context.card_is_primary:
        return "request_update", "Non-primary card failing, request update"

    # Default - retry same card
    return "same_card", "Standard retry with same payment method"


@activity.defn
async def predict_retry_strategy(
    enriched_context: EnrichedPaymentContext | dict,
    failure_code: str,
    attempt: int,
) -> RetryPrediction:
    """
    Predict the optimal retry strategy using ML-like rules.

    This activity simulates what Butter's ML models would do - analyze
    hundreds of variables to determine the optimal retry timing and method.

    Args:
        enriched_context: Payment context with ML features
        failure_code: The current failure code
        attempt: Current retry attempt number (1-based)

    Returns:
        RetryPrediction with recommended strategy
    """
    activity.logger.info(
        f"Predicting retry strategy for failure={failure_code}, attempt={attempt}"
    )

    # Handle both dataclass and dict inputs
    if isinstance(enriched_context, dict):
        context = EnrichedPaymentContext(**enriched_context)
    else:
        context = enriched_context

    factors: list[str] = []

    # Determine retry method and reason
    method, reason = _determine_retry_method(failure_code, context, attempt)

    # If we're not retrying, return early
    if method == "give_up":
        return RetryPrediction(
            should_retry=False,
            delay_hours=0,
            retry_method=method,
            confidence=0.9,
            model_version=MODEL_VERSION,
            reason=reason,
            factors=["non_retryable"],
        )

    # If requesting update or dunning, still counts as "retry" but different method
    if method in ("request_update", "dunning_email"):
        return RetryPrediction(
            should_retry=False,  # Not auto-retrying
            delay_hours=0,
            retry_method=method,
            confidence=0.8,
            model_version=MODEL_VERSION,
            reason=reason,
            factors=factors or ["customer_action_required"],
        )

    # Compute optimal delay
    base_delay = _compute_base_delay(failure_code, attempt)
    factors.append(f"base_delay_{base_delay}h")

    adjusted_delay = _adjust_delay_for_context(base_delay, context, factors)

    # Compute confidence
    confidence = _compute_confidence(context, failure_code, attempt)

    prediction = RetryPrediction(
        should_retry=True,
        delay_hours=round(adjusted_delay, 1),
        retry_method=method,
        confidence=confidence,
        model_version=MODEL_VERSION,
        reason=f"Retry in {adjusted_delay:.1f}h with {method}",
        factors=factors,
    )

    activity.logger.info(
        f"Prediction: retry={prediction.should_retry}, "
        f"delay={prediction.delay_hours}h, method={prediction.retry_method}, "
        f"confidence={prediction.confidence:.1%}"
    )

    return prediction
