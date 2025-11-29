"""Retry strategy endpoint."""

import asyncio
import logging
import random
from enum import Enum

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class RetryAction(str, Enum):
    """Recommended retry action."""

    RETRY_NOW = "retry_now"
    RETRY_DELAYED = "retry_delayed"
    DO_NOT_RETRY = "do_not_retry"
    CONTACT_CUSTOMER = "contact_customer"


class RetryStrategyRequest(BaseModel):
    """Request payload for retry strategy."""

    event_id: str = Field(..., description="Payment event ID")
    failure_code: str | None = Field(default=None, description="Payment failure code")
    failure_message: str | None = Field(default=None, description="Payment failure message")
    amount_cents: int = Field(..., ge=0, description="Payment amount in cents")
    attempt_count: int = Field(default=1, ge=1, description="Number of attempts so far")


class RetryStrategyResponse(BaseModel):
    """Response payload from retry strategy."""

    event_id: str
    action: RetryAction
    delay_seconds: int | None = None
    max_attempts: int = 5
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str


# Failure codes that should never be retried
NON_RETRYABLE_CODES = {
    "card_declined",
    "expired_card",
    "fraudulent",
    "stolen_card",
    "lost_card",
    "card_not_supported",
    "currency_not_supported",
    "do_not_honor",
    "generic_decline",
    "invalid_account",
    "invalid_amount",
    "invalid_card_number",
    "pickup_card",
    "restricted_card",
    "security_violation",
}

# Failure codes that require customer action
CUSTOMER_ACTION_CODES = {
    "insufficient_funds",
    "withdrawal_count_limit_exceeded",
    "card_velocity_exceeded",
    "authentication_required",
    "approve_with_id",
}

# Transient failures that can be retried
TRANSIENT_CODES = {
    "processing_error",
    "issuer_not_available",
    "try_again_later",
    "reenter_transaction",
    "network_error",
    "timeout",
}


def compute_retry_strategy(request: RetryStrategyRequest) -> tuple[RetryAction, int | None, float, str]:
    """
    Compute retry strategy based on failure code and attempt count.

    Returns:
        Tuple of (action, delay_seconds, confidence, reason)
    """
    failure_code = (request.failure_code or "").lower().replace(" ", "_")

    # Check for non-retryable codes
    if failure_code in NON_RETRYABLE_CODES:
        return (
            RetryAction.DO_NOT_RETRY,
            None,
            0.95,
            f"Failure code '{failure_code}' is not retryable",
        )

    # Check for customer action required
    if failure_code in CUSTOMER_ACTION_CODES:
        return (
            RetryAction.CONTACT_CUSTOMER,
            None,
            0.90,
            f"Failure code '{failure_code}' requires customer action",
        )

    # Check max attempts
    max_attempts = 5
    if request.attempt_count >= max_attempts:
        return (
            RetryAction.DO_NOT_RETRY,
            None,
            0.85,
            f"Maximum attempts ({max_attempts}) reached",
        )

    # Transient failures - retry with exponential backoff
    if failure_code in TRANSIENT_CODES or not failure_code:
        # Exponential backoff: 2^(attempt-1) * base_delay, capped at 1 hour
        base_delay = 60  # 1 minute
        delay = min(base_delay * (2 ** (request.attempt_count - 1)), 3600)
        return (
            RetryAction.RETRY_DELAYED,
            delay,
            0.75,
            f"Transient failure, retry in {delay}s (attempt {request.attempt_count}/{max_attempts})",
        )

    # Unknown failure code - conservative retry
    delay = min(120 * request.attempt_count, 3600)  # Linear backoff for unknown codes
    return (
        RetryAction.RETRY_DELAYED,
        delay,
        0.60,
        f"Unknown failure code '{failure_code}', conservative retry in {delay}s",
    )


@router.post("/strategy", response_model=RetryStrategyResponse)
async def get_retry_strategy(request: RetryStrategyRequest) -> RetryStrategyResponse:
    """
    Get retry strategy for a failed payment.

    This is a mock implementation that uses rule-based decision making.
    """
    logger.info(
        f"Computing retry strategy for event: {request.event_id}, "
        f"failure_code: {request.failure_code}, attempt: {request.attempt_count}"
    )

    # Simulate processing latency
    latency = random.randint(settings.min_latency_ms, settings.max_latency_ms) / 1000
    await asyncio.sleep(latency)

    action, delay, confidence, reason = compute_retry_strategy(request)

    logger.info(
        f"Retry strategy for {request.event_id}: {action.value}, "
        f"delay: {delay}s, confidence: {confidence}"
    )

    return RetryStrategyResponse(
        event_id=request.event_id,
        action=action,
        delay_seconds=delay,
        max_attempts=5,
        confidence=confidence,
        reason=reason,
    )
