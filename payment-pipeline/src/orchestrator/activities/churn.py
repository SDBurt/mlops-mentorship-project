"""Churn prediction activity."""

from typing import Any

import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from ..config import settings


@activity.defn
async def get_churn_prediction(event_data: dict[str, Any]) -> dict[str, Any]:
    """
    Get churn prediction from the inference service.

    Args:
        event_data: Normalized payment event data

    Returns:
        Churn prediction result with probability and risk factors

    Raises:
        ApplicationError: If the inference service is unavailable or returns an error
    """
    event_id = event_data.get("event_id", "unknown")
    customer_id = event_data.get("customer_id")

    if not customer_id:
        activity.logger.info(f"No customer_id for {event_id}, skipping churn prediction")
        return {
            "churn_score": None,
            "churn_risk_level": None,
            "churn_risk_factors": [],
            "days_to_churn_estimate": None,
        }

    activity.logger.info(f"Getting churn prediction for customer: {customer_id}")

    # Build request payload
    # Note: In production, you'd fetch customer history from a database
    # For now, we use defaults with some signals from the event
    payload = {
        "customer_id": customer_id,
        "merchant_id": event_data.get("merchant_id"),
        # Default values - in production, fetch from customer history
        "total_payments": 10,
        "successful_payments": 8,
        "failed_payments": 2,
        "recovered_payments": 1,
        "days_since_last_payment": 5,
        "days_since_last_failure": 30,
        "consecutive_failures": 0,
        "subscription_age_days": 180,
        "payment_method_age_days": 90,
        "has_backup_payment_method": False,
    }

    # Adjust based on current event status
    status = event_data.get("status", "").lower()
    if "failed" in status or "declined" in status:
        payload["consecutive_failures"] = 1
        payload["days_since_last_failure"] = 0

    try:
        async with httpx.AsyncClient(timeout=settings.inference_timeout_seconds) as client:
            response = await client.post(
                f"{settings.inference_service_url}/churn/predict",
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            activity.logger.info(
                f"Churn prediction for {customer_id}: {result.get('churn_probability')} "
                f"({result.get('risk_level')})"
            )

            return {
                "churn_score": result.get("churn_probability"),
                "churn_risk_level": result.get("risk_level"),
                "churn_risk_factors": result.get("risk_factors", []),
                "days_to_churn_estimate": result.get("days_to_churn_estimate"),
                "churn_recommended_actions": result.get("recommended_actions", []),
            }

    except httpx.TimeoutException as e:
        activity.logger.error(f"Churn service timeout for {customer_id}: {e}")
        raise ApplicationError(
            f"Churn service timeout after {settings.inference_timeout_seconds}s",
            non_retryable=False,
        )

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        activity.logger.error(f"Churn service error for {customer_id}: {status_code}")

        non_retryable = status_code < 500
        raise ApplicationError(
            f"Churn service returned {status_code}",
            non_retryable=non_retryable,
        )

    except httpx.RequestError as e:
        activity.logger.error(f"Churn service connection error for {customer_id}: {e}")
        raise ApplicationError(
            f"Failed to connect to churn service: {e}",
            non_retryable=False,
        )
