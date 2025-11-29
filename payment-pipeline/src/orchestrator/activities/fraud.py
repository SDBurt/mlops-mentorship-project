"""Fraud scoring activity."""

from typing import Any

import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from ..config import settings


@activity.defn
async def get_fraud_score(event_data: dict[str, Any]) -> dict[str, Any]:
    """
    Get fraud score from the inference service.

    Args:
        event_data: Normalized payment event data

    Returns:
        Fraud scoring result with score and risk factors

    Raises:
        ApplicationError: If the inference service is unavailable or returns an error
    """
    event_id = event_data.get("event_id", "unknown")
    activity.logger.info(f"Getting fraud score for: {event_id}")

    # Build request payload
    payload = {
        "event_id": event_id,
        "amount_cents": event_data.get("amount_cents", 0),
        "currency": event_data.get("currency", "USD"),
        "customer_id": event_data.get("customer_id"),
        "merchant_id": event_data.get("merchant_id"),
        "payment_method_type": event_data.get("payment_method_type"),
        "card_brand": event_data.get("card_brand"),
    }

    try:
        async with httpx.AsyncClient(timeout=settings.inference_timeout_seconds) as client:
            response = await client.post(
                f"{settings.inference_service_url}/fraud/score",
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            activity.logger.info(
                f"Fraud score for {event_id}: {result.get('fraud_score')} "
                f"({result.get('risk_level')})"
            )

            return {
                "fraud_score": result.get("fraud_score"),
                "risk_level": result.get("risk_level"),
                "risk_factors": result.get("risk_factors", []),
                "model_version": result.get("model_version"),
            }

    except httpx.TimeoutException as e:
        activity.logger.error(f"Fraud service timeout for {event_id}: {e}")
        raise ApplicationError(
            f"Fraud service timeout after {settings.inference_timeout_seconds}s",
            non_retryable=False,
        )

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        activity.logger.error(f"Fraud service error for {event_id}: {status_code}")

        # 4xx errors are non-retryable (client errors)
        # 5xx errors are retryable (server errors)
        # Exception: 429 (Too Many Requests) is retryable
        non_retryable = status_code < 500 and status_code != 429
        raise ApplicationError(
            f"Fraud service returned {status_code}",
            non_retryable=non_retryable,
        )

    except httpx.RequestError as e:
        activity.logger.error(f"Fraud service connection error for {event_id}: {e}")
        raise ApplicationError(
            f"Failed to connect to fraud service: {e}",
            non_retryable=False,
        )
