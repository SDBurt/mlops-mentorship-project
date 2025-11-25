# temporal/activities/retry_strategy.py
from temporalio import activity
from dataclasses import dataclass
import httpx

@dataclass
class RetryStrategy:
    should_retry: bool
    delay_hours: int
    method: str
    max_attempts: int

@activity.defn
async def get_retry_strategy(payment_data: dict, failure_code: str, attempt: int) -> RetryStrategy:
    """
    Calls ML service to determine optimal retry strategy.
    This is where Butter's ML magic would happen.
    """
    activity.logger.info(f"Getting retry strategy for {failure_code}, attempt {attempt}")

    # In production, call your ML inference service:
    # async with httpx.AsyncClient() as client:
    #     response = await client.post(
    #         "http://ml-service:8000/retry-strategy",
    #         json={"payment": payment_data, "failure": failure_code, "attempt": attempt}
    #     )
    #     return RetryStrategy(**response.json())

    # For now, rules-based fallback
    strategies = {
        "card_declined": RetryStrategy(True, 24, "same_card", 3),
        "insufficient_funds": RetryStrategy(True, 48, "same_card", 5),
        "expired_card": RetryStrategy(False, 0, "request_update", 0),
        "incorrect_cvc": RetryStrategy(True, 1, "same_card", 2),
        "processing_error": RetryStrategy(True, 6, "same_card", 3),
    }

    strategy = strategies.get(
        failure_code,
        RetryStrategy(True, 24, "same_card", 3)
    )

    # Reduce retries if we've already tried multiple times
    if attempt >= strategy.max_attempts:
        return RetryStrategy(False, 0, "give_up", 0)

    return strategy
