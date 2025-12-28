"""Retry strategy activity."""

from typing import Any

import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from ..config import settings


@activity.defn
async def get_retry_strategy(event_data: dict[str, Any]) -> dict[str, Any]:
    """
    Get retry strategy from the inference service for failed payments.

    Args:
        event_data: Normalized payment event data (must be a failed payment)

    Returns:
        Retry strategy with recommended action and timing

    Raises:
        ApplicationError: If the inference service is unavailable or returns an error
    """
    event_id = event_data.get("event_id", "unknown")
    activity.logger.info(f"Getting retry strategy for: {event_id}")

    # Extract attempt count from metadata if available
    metadata = event_data.get("metadata", {})
    attempt_count = metadata.get("retry_attempt_count", 1)

    # Build request payload
    payload = {
        "event_id": event_id,
        "failure_code": event_data.get("failure_code"),
        "failure_message": event_data.get("failure_message"),
        "amount_cents": event_data.get("amount_cents", 0),
        "attempt_count": attempt_count,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.inference_timeout_seconds) as client:
            response = await client.post(
                f"{settings.inference_service_url}/retry/strategy",
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            activity.logger.info(
                f"Retry strategy for {event_id}: {result.get('action')} "
                f"(confidence: {result.get('confidence')})"
            )

            return {
                "action": result.get("action"),
                "delay_seconds": result.get("delay_seconds"),
                "max_attempts": result.get("max_attempts"),
                "confidence": result.get("confidence"),
                "reason": result.get("reason"),
            }

    except httpx.TimeoutException as e:
        activity.logger.error(f"Retry service timeout for {event_id}: {e}")
        raise ApplicationError(
            f"Retry service timeout after {settings.inference_timeout_seconds}s",
            non_retryable=False,
        )

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        activity.logger.error(f"Retry service error for {event_id}: {status_code}")

        # 4xx errors are non-retryable (client errors)
        # 5xx errors are retryable (server errors)
        non_retryable = status_code < 500
        raise ApplicationError(
            f"Retry service returned {status_code}",
            non_retryable=non_retryable,
        )

    except httpx.RequestError as e:
        activity.logger.error(f"Retry service connection error for {event_id}: {e}")
        raise ApplicationError(
            f"Failed to connect to retry service: {e}",
            non_retryable=False,
        )
