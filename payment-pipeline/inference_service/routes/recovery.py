"""Payment recovery endpoint."""

import asyncio
import logging
import random
from datetime import datetime, timezone
from enum import Enum

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class RecoveryAction(str, Enum):
    """Recommended recovery action."""

    RETRY_IMMEDIATELY = "retry_immediately"
    RETRY_OPTIMAL_TIME = "retry_optimal_time"
    UPDATE_PAYMENT_METHOD = "update_payment_method"
    DUNNING_EMAIL = "dunning_email"
    SMS_REMINDER = "sms_reminder"
    OFFER_ALTERNATIVE = "offer_alternative"
    PAUSE_SUBSCRIPTION = "pause_subscription"
    ESCALATE_TO_SUPPORT = "escalate_to_support"
    WRITE_OFF = "write_off"


class RecoveryPriority(str, Enum):
    """Recovery priority level."""

    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PaymentRecoveryRequest(BaseModel):
    """Request payload for payment recovery recommendation."""

    event_id: str = Field(..., description="Failed payment event ID")
    customer_id: str = Field(..., description="Customer identifier")
    merchant_id: str | None = Field(default=None, description="Merchant identifier")

    # Payment details
    amount_cents: int = Field(..., ge=0, description="Failed payment amount in cents")
    currency: str = Field(default="USD", description="Currency code")
    failure_code: str | None = Field(default=None, description="Payment failure code")
    failure_message: str | None = Field(default=None, description="Failure message")

    # Retry context
    attempt_number: int = Field(default=1, ge=1, description="Current attempt number")
    max_attempts: int = Field(default=5, ge=1, description="Maximum retry attempts")
    hours_since_first_failure: float = Field(default=0, ge=0, description="Hours since first failure")

    # Customer context
    customer_lifetime_value_cents: int = Field(default=0, ge=0, description="Customer LTV")
    subscription_tier: str | None = Field(default=None, description="Subscription tier (free, pro, enterprise)")
    has_valid_email: bool = Field(default=True, description="Has valid email for notifications")
    has_valid_phone: bool = Field(default=False, description="Has valid phone for SMS")
    preferred_contact_method: str | None = Field(default=None, description="Preferred contact method")

    # Payment method context
    payment_method_type: str | None = Field(default=None, description="Payment method type")
    card_brand: str | None = Field(default=None, description="Card brand")
    card_exp_month: int | None = Field(default=None, ge=1, le=12, description="Card expiry month")
    card_exp_year: int | None = Field(default=None, description="Card expiry year")
    has_backup_payment_method: bool = Field(default=False, description="Has backup payment method")


class RecoveryStep(BaseModel):
    """A single step in the recovery plan."""

    action: RecoveryAction
    delay_hours: float = Field(default=0, description="Hours to wait before this step")
    reason: str
    expected_success_rate: float = Field(ge=0.0, le=1.0, description="Expected success rate")


class PaymentRecoveryResponse(BaseModel):
    """Response payload from payment recovery recommendation."""

    event_id: str
    customer_id: str
    priority: RecoveryPriority
    primary_action: RecoveryAction
    recovery_plan: list[RecoveryStep]
    optimal_retry_hour_utc: int | None = Field(
        default=None,
        ge=0, le=23,
        description="Optimal hour (UTC) to retry payment"
    )
    estimated_recovery_probability: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    insights: list[str] = Field(default_factory=list)
    model_version: str = Field(default="mock-v1")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# Failure codes that indicate card issues requiring customer action
CARD_UPDATE_REQUIRED = {
    "expired_card",
    "invalid_card_number",
    "card_declined",
    "lost_card",
    "stolen_card",
    "pickup_card",
}

# Transient failures that often succeed on retry
TRANSIENT_FAILURES = {
    "processing_error",
    "issuer_not_available",
    "try_again_later",
    "network_error",
    "timeout",
}

# Failures requiring customer contact
CUSTOMER_ACTION_REQUIRED = {
    "insufficient_funds",
    "withdrawal_count_limit_exceeded",
    "card_velocity_exceeded",
    "authentication_required",
}


def is_card_expired(exp_month: int | None, exp_year: int | None) -> bool:
    """Check if card is expired."""
    if not exp_month or not exp_year:
        return False

    now = datetime.now(timezone.utc)
    # Card expires at end of the expiry month
    if exp_year < now.year:
        return True
    if exp_year == now.year and exp_month < now.month:
        return True
    return False


def compute_optimal_retry_hour(failure_code: str | None, amount_cents: int) -> int:
    """
    Compute optimal hour (UTC) to retry payment.

    Based on patterns:
    - Insufficient funds: Retry after payday (beginning/middle of month, morning hours)
    - High amounts: Retry during business hours
    - General: Avoid late night retries
    """
    failure_code = (failure_code or "").lower()

    if "insufficient_funds" in failure_code:
        # Morning hours when bank transfers typically clear
        return 9

    if amount_cents > 50_000_00:  # High value payments
        # Business hours for potential manual intervention
        return 14

    # Default: Mid-morning for best success rates
    return 10


def compute_recovery_plan(request: PaymentRecoveryRequest) -> tuple[
    RecoveryPriority,
    RecoveryAction,
    list[RecoveryStep],
    float,
    list[str]
]:
    """
    Compute recovery plan based on failure context.

    Returns:
        Tuple of (priority, primary_action, recovery_steps, success_probability, insights)
    """
    failure_code = (request.failure_code or "").lower().replace(" ", "_")
    insights = []
    recovery_steps = []
    base_success_prob = 0.5

    # Determine priority based on LTV and subscription tier
    if request.customer_lifetime_value_cents > 100_000_00:  # > $1000 LTV
        priority = RecoveryPriority.URGENT
        insights.append("High-value customer requires priority recovery")
    elif request.subscription_tier in ["enterprise", "pro"]:
        priority = RecoveryPriority.HIGH
        insights.append(f"Premium tier ({request.subscription_tier}) customer")
    elif request.attempt_number >= 3:
        priority = RecoveryPriority.HIGH
        insights.append("Multiple failed attempts - escalating priority")
    else:
        priority = RecoveryPriority.MEDIUM

    # Check for expired card
    if is_card_expired(request.card_exp_month, request.card_exp_year):
        insights.append("Card is expired")
        recovery_steps.append(RecoveryStep(
            action=RecoveryAction.UPDATE_PAYMENT_METHOD,
            delay_hours=0,
            reason="Card has expired and must be updated",
            expected_success_rate=0.0,
        ))
        if request.has_valid_email:
            recovery_steps.append(RecoveryStep(
                action=RecoveryAction.DUNNING_EMAIL,
                delay_hours=0.5,
                reason="Send card update request email",
                expected_success_rate=0.35,
            ))
        if request.has_valid_phone:
            recovery_steps.append(RecoveryStep(
                action=RecoveryAction.SMS_REMINDER,
                delay_hours=24,
                reason="Follow up with SMS if no response",
                expected_success_rate=0.25,
            ))
        return priority, RecoveryAction.UPDATE_PAYMENT_METHOD, recovery_steps, 0.35, insights

    # Handle card issues requiring update
    if failure_code in CARD_UPDATE_REQUIRED:
        insights.append(f"Card issue ({failure_code}) requires customer action")
        base_success_prob = 0.30

        recovery_steps.append(RecoveryStep(
            action=RecoveryAction.DUNNING_EMAIL,
            delay_hours=0,
            reason=f"Notify customer of {failure_code}",
            expected_success_rate=0.30,
        ))

        if request.has_backup_payment_method:
            recovery_steps.insert(0, RecoveryStep(
                action=RecoveryAction.OFFER_ALTERNATIVE,
                delay_hours=0,
                reason="Try backup payment method first",
                expected_success_rate=0.65,
            ))
            base_success_prob = 0.65
            insights.append("Backup payment method available")

        return priority, RecoveryAction.UPDATE_PAYMENT_METHOD, recovery_steps, base_success_prob, insights

    # Handle transient failures - can retry
    if failure_code in TRANSIENT_FAILURES:
        insights.append(f"Transient failure ({failure_code}) - good retry candidate")
        base_success_prob = 0.70

        # Calculate delay based on attempt number (exponential backoff)
        retry_delay = min(2 ** (request.attempt_number - 1), 24)

        recovery_steps.append(RecoveryStep(
            action=RecoveryAction.RETRY_OPTIMAL_TIME,
            delay_hours=retry_delay,
            reason=f"Retry after {retry_delay}h for transient failure",
            expected_success_rate=0.70 - (0.10 * request.attempt_number),
        ))

        if request.attempt_number >= 3:
            recovery_steps.append(RecoveryStep(
                action=RecoveryAction.DUNNING_EMAIL,
                delay_hours=retry_delay + 24,
                reason="Notify customer after multiple failures",
                expected_success_rate=0.20,
            ))

        return priority, RecoveryAction.RETRY_OPTIMAL_TIME, recovery_steps, base_success_prob, insights

    # Handle insufficient funds
    if failure_code in CUSTOMER_ACTION_REQUIRED:
        insights.append(f"Customer action required ({failure_code})")
        base_success_prob = 0.45

        # Wait for funds (retry near payday)
        recovery_steps.append(RecoveryStep(
            action=RecoveryAction.RETRY_OPTIMAL_TIME,
            delay_hours=24,
            reason="Wait for funds to become available",
            expected_success_rate=0.45,
        ))

        if request.has_valid_email:
            recovery_steps.append(RecoveryStep(
                action=RecoveryAction.DUNNING_EMAIL,
                delay_hours=48,
                reason="Send friendly reminder about payment",
                expected_success_rate=0.30,
            ))

        if request.has_backup_payment_method:
            recovery_steps.insert(0, RecoveryStep(
                action=RecoveryAction.OFFER_ALTERNATIVE,
                delay_hours=0,
                reason="Offer to use backup payment method",
                expected_success_rate=0.55,
            ))
            base_success_prob = 0.55
            insights.append("Backup payment method available")

        return priority, RecoveryAction.RETRY_OPTIMAL_TIME, recovery_steps, base_success_prob, insights

    # Default recovery plan for unknown failures
    insights.append(f"Unknown failure code: {failure_code or 'none'}")

    recovery_steps = [
        RecoveryStep(
            action=RecoveryAction.RETRY_OPTIMAL_TIME,
            delay_hours=4,
            reason="Standard retry after cooling period",
            expected_success_rate=0.50,
        ),
        RecoveryStep(
            action=RecoveryAction.DUNNING_EMAIL,
            delay_hours=24,
            reason="Follow up with payment reminder",
            expected_success_rate=0.25,
        ),
    ]

    # Late-stage recovery
    if request.attempt_number >= request.max_attempts - 1:
        recovery_steps.append(RecoveryStep(
            action=RecoveryAction.ESCALATE_TO_SUPPORT,
            delay_hours=48,
            reason="Escalate to support before final attempt",
            expected_success_rate=0.15,
        ))

    return priority, RecoveryAction.RETRY_OPTIMAL_TIME, recovery_steps, 0.50, insights


@router.post("/recommend", response_model=PaymentRecoveryResponse)
async def recommend_recovery(request: PaymentRecoveryRequest) -> PaymentRecoveryResponse:
    """
    Get payment recovery recommendation for a failed payment.

    This endpoint analyzes the failure context and customer signals to
    recommend the optimal recovery strategy to minimize involuntary churn.
    """
    logger.info(
        f"Computing recovery for event: {request.event_id}, "
        f"customer: {request.customer_id}, failure: {request.failure_code}"
    )

    # Simulate processing latency
    latency = random.randint(settings.min_latency_ms, settings.max_latency_ms) / 1000
    await asyncio.sleep(latency)

    priority, primary_action, recovery_plan, success_prob, insights = compute_recovery_plan(request)
    optimal_hour = compute_optimal_retry_hour(request.failure_code, request.amount_cents)

    # Compute confidence based on data completeness
    confidence = 0.6
    if request.failure_code:
        confidence += 0.15
    if request.customer_lifetime_value_cents > 0:
        confidence += 0.10
    if request.has_valid_email or request.has_valid_phone:
        confidence += 0.10
    confidence = min(confidence, 0.95)

    logger.info(
        f"Recovery recommendation for {request.event_id}: {primary_action.value}, "
        f"priority: {priority.value}, success_prob: {success_prob:.2%}"
    )

    return PaymentRecoveryResponse(
        event_id=request.event_id,
        customer_id=request.customer_id,
        priority=priority,
        primary_action=primary_action,
        recovery_plan=recovery_plan,
        optimal_retry_hour_utc=optimal_hour,
        estimated_recovery_probability=success_prob,
        confidence=confidence,
        insights=insights,
        model_version=settings.model_version,
    )
