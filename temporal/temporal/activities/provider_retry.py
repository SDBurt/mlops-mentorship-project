# temporal/activities/provider_retry.py
"""
Provider retry activity.

Executes payment retries via the original provider's API.
This simulates calling Stripe, Square, or Braintree APIs to retry failed payments.
"""
import random
import string
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Protocol

from temporalio import activity

from temporal.activities.normalize_event import NormalizedFailedPayment
from temporal.providers.base import FailureCode


@dataclass
class RetryResult:
    """Result of a provider retry attempt."""
    success: bool
    provider: str
    provider_response: dict  # Raw provider response
    new_charge_id: str | None  # New charge ID if successful
    error_code: str | None  # Normalized error code if failed
    error_message: str | None  # Human-readable error message
    retry_timestamp: str  # ISO 8601

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for workflow."""
        return asdict(self)


class ProviderRetryClient(ABC):
    """Abstract base class for provider retry clients."""

    @abstractmethod
    async def retry_payment(
        self,
        payment_id: str,
        amount_cents: int,
        currency: str,
        metadata: dict,
    ) -> dict:
        """
        Attempt to retry a payment via the provider's API.

        Returns:
            Provider-specific response dict
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider name."""
        pass


class StripeRetryClient(ProviderRetryClient):
    """Simulated Stripe API client for retries."""

    # Stripe retry success rate based on attempt number
    SUCCESS_RATES = {
        1: 0.45,  # First retry succeeds 45% of time
        2: 0.30,
        3: 0.20,
        4: 0.15,
        5: 0.10,
    }

    def get_provider_name(self) -> str:
        return "stripe"

    def _generate_id(self, prefix: str, length: int = 24) -> str:
        chars = string.ascii_letters + string.digits
        return f"{prefix}_{''.join(random.choices(chars, k=length))}"

    async def retry_payment(
        self,
        payment_id: str,
        amount_cents: int,
        currency: str,
        metadata: dict,
    ) -> dict:
        """Simulate a Stripe PaymentIntent confirmation."""
        attempt = metadata.get("retry_count", 0) + 1
        success_rate = self.SUCCESS_RATES.get(attempt, 0.10)

        is_success = random.random() < success_rate

        if is_success:
            return {
                "id": self._generate_id("ch"),
                "object": "charge",
                "amount": amount_cents,
                "currency": currency.lower(),
                "status": "succeeded",
                "paid": True,
                "captured": True,
                "created": int(datetime.utcnow().timestamp()),
                "payment_intent": payment_id,
                "outcome": {
                    "network_status": "approved_by_network",
                    "reason": None,
                    "risk_level": "normal",
                    "seller_message": "Payment complete.",
                    "type": "authorized",
                },
            }
        else:
            # Generate realistic Stripe decline response
            decline_codes = [
                ("card_declined", "Your card was declined."),
                ("insufficient_funds", "Your card has insufficient funds."),
                ("processing_error", "An error occurred while processing your card."),
            ]
            code, message = random.choice(decline_codes)

            return {
                "id": self._generate_id("ch"),
                "object": "charge",
                "amount": amount_cents,
                "currency": currency.lower(),
                "status": "failed",
                "paid": False,
                "captured": False,
                "created": int(datetime.utcnow().timestamp()),
                "payment_intent": payment_id,
                "failure_code": code,
                "failure_message": message,
                "outcome": {
                    "network_status": "declined_by_network",
                    "reason": code,
                    "risk_level": "normal",
                    "seller_message": message,
                    "type": "issuer_declined",
                },
            }


class SquareRetryClient(ProviderRetryClient):
    """Simulated Square API client for retries."""

    SUCCESS_RATES = {
        1: 0.42,
        2: 0.28,
        3: 0.18,
        4: 0.12,
        5: 0.08,
    }

    def get_provider_name(self) -> str:
        return "square"

    def _generate_id(self, length: int = 22) -> str:
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choices(chars, k=length))

    async def retry_payment(
        self,
        payment_id: str,
        amount_cents: int,
        currency: str,
        metadata: dict,
    ) -> dict:
        """Simulate a Square CreatePayment retry."""
        attempt = metadata.get("retry_count", 0) + 1
        success_rate = self.SUCCESS_RATES.get(attempt, 0.08)

        is_success = random.random() < success_rate

        if is_success:
            return {
                "payment": {
                    "id": self._generate_id(),
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                    "amount_money": {
                        "amount": amount_cents,
                        "currency": currency.upper(),
                    },
                    "status": "COMPLETED",
                    "source_type": "CARD",
                    "card_details": {
                        "status": "CAPTURED",
                        "card": {"card_brand": "VISA", "last_4": "1234"},
                    },
                },
            }
        else:
            error_codes = [
                ("GENERIC_DECLINE", "Card declined by issuer."),
                ("INSUFFICIENT_FUNDS", "Insufficient funds in account."),
                ("CVV_FAILURE", "CVV verification failed."),
            ]
            code, message = random.choice(error_codes)

            return {
                "errors": [{
                    "code": code,
                    "detail": message,
                    "category": "PAYMENT_METHOD_ERROR",
                }],
                "payment": {
                    "id": self._generate_id(),
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "amount_money": {
                        "amount": amount_cents,
                        "currency": currency.upper(),
                    },
                    "status": "FAILED",
                    "card_details": {
                        "status": "FAILED",
                        "errors": [{"code": code, "detail": message}],
                    },
                },
            }


class BraintreeRetryClient(ProviderRetryClient):
    """Simulated Braintree API client for retries."""

    SUCCESS_RATES = {
        1: 0.48,
        2: 0.32,
        3: 0.22,
        4: 0.14,
        5: 0.09,
    }

    def get_provider_name(self) -> str:
        return "braintree"

    def _generate_id(self, length: int = 8) -> str:
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choices(chars, k=length))

    async def retry_payment(
        self,
        payment_id: str,
        amount_cents: int,
        currency: str,
        metadata: dict,
    ) -> dict:
        """Simulate a Braintree Transaction.sale retry."""
        attempt = metadata.get("retry_count", 0) + 1
        success_rate = self.SUCCESS_RATES.get(attempt, 0.09)

        is_success = random.random() < success_rate

        # Braintree uses decimal strings
        amount_str = str(amount_cents / 100)

        if is_success:
            return {
                "success": True,
                "transaction": {
                    "id": self._generate_id(),
                    "status": "submitted_for_settlement",
                    "type": "sale",
                    "currencyIsoCode": currency.upper(),
                    "amount": amount_str,
                    "processorResponseCode": "1000",
                    "processorResponseText": "Approved",
                    "createdAt": datetime.utcnow().isoformat(),
                },
            }
        else:
            error_codes = [
                ("2000", "Do Not Honor"),
                ("2001", "Insufficient Funds"),
                ("2046", "Declined"),
            ]
            code, message = random.choice(error_codes)

            return {
                "success": False,
                "transaction": {
                    "id": self._generate_id(),
                    "status": "processor_declined",
                    "type": "sale",
                    "currencyIsoCode": currency.upper(),
                    "amount": amount_str,
                    "processorResponseCode": code,
                    "processorResponseText": message,
                    "createdAt": datetime.utcnow().isoformat(),
                },
                "errors": {
                    "errorDetails": [{
                        "code": code,
                        "message": message,
                    }],
                },
            }


# Client registry
_clients: dict[str, ProviderRetryClient] = {
    "stripe": StripeRetryClient(),
    "square": SquareRetryClient(),
    "braintree": BraintreeRetryClient(),
}


def _parse_stripe_response(response: dict) -> RetryResult:
    """Parse Stripe API response into RetryResult."""
    is_success = response.get("status") == "succeeded"

    error_code = None
    error_message = None
    if not is_success:
        failure_code = response.get("failure_code", "card_declined")
        error_code = FailureCode.STRIPE_MAPPING.get(failure_code, FailureCode.CARD_DECLINED)
        error_message = response.get("failure_message", "Payment failed")

    return RetryResult(
        success=is_success,
        provider="stripe",
        provider_response=response,
        new_charge_id=response.get("id") if is_success else None,
        error_code=error_code,
        error_message=error_message,
        retry_timestamp=datetime.utcnow().isoformat() + "Z",
    )


def _parse_square_response(response: dict) -> RetryResult:
    """Parse Square API response into RetryResult."""
    payment = response.get("payment", {})
    errors = response.get("errors", [])

    is_success = payment.get("status") == "COMPLETED" and not errors

    error_code = None
    error_message = None
    if not is_success and errors:
        first_error = errors[0]
        sq_code = first_error.get("code", "GENERIC_DECLINE")
        error_code = FailureCode.SQUARE_MAPPING.get(sq_code, FailureCode.CARD_DECLINED)
        error_message = first_error.get("detail", "Payment failed")

    return RetryResult(
        success=is_success,
        provider="square",
        provider_response=response,
        new_charge_id=payment.get("id") if is_success else None,
        error_code=error_code,
        error_message=error_message,
        retry_timestamp=datetime.utcnow().isoformat() + "Z",
    )


def _parse_braintree_response(response: dict) -> RetryResult:
    """Parse Braintree API response into RetryResult."""
    is_success = response.get("success", False)
    transaction = response.get("transaction", {})

    error_code = None
    error_message = None
    if not is_success:
        bt_code = transaction.get("processorResponseCode", "2000")
        error_code = FailureCode.BRAINTREE_MAPPING.get(bt_code, FailureCode.CARD_DECLINED)
        error_message = transaction.get("processorResponseText", "Transaction declined")

    return RetryResult(
        success=is_success,
        provider="braintree",
        provider_response=response,
        new_charge_id=transaction.get("id") if is_success else None,
        error_code=error_code,
        error_message=error_message,
        retry_timestamp=datetime.utcnow().isoformat() + "Z",
    )


@activity.defn
async def execute_provider_retry(
    normalized_payment: NormalizedFailedPayment | dict,
    retry_method: str,
) -> RetryResult:
    """
    Execute a payment retry via the original provider's API.

    This activity simulates calling the provider's API (Stripe, Square, Braintree)
    to retry a failed payment.

    Args:
        normalized_payment: The normalized failed payment to retry
        retry_method: The retry method from prediction ("same_card", etc.)

    Returns:
        RetryResult with success/failure and provider response
    """
    # Handle both dataclass and dict inputs
    if isinstance(normalized_payment, dict):
        payment = NormalizedFailedPayment(**normalized_payment)
    else:
        payment = normalized_payment

    activity.logger.info(
        f"Executing provider retry: provider={payment.provider}, "
        f"payment_id={payment.provider_payment_id}, method={retry_method}"
    )

    # Get the appropriate client
    provider = payment.provider.lower()
    client = _clients.get(provider)

    if not client:
        activity.logger.error(f"Unknown provider: {provider}")
        return RetryResult(
            success=False,
            provider=provider,
            provider_response={"error": f"Unknown provider: {provider}"},
            new_charge_id=None,
            error_code=FailureCode.PROCESSING_ERROR,
            error_message=f"Unknown provider: {provider}",
            retry_timestamp=datetime.utcnow().isoformat() + "Z",
        )

    # Prepare metadata
    metadata = {
        "retry_count": payment.retry_count,
        "retry_method": retry_method,
        "original_charge_id": payment.original_charge_id,
    }

    # Execute the retry
    response = await client.retry_payment(
        payment_id=payment.provider_payment_id,
        amount_cents=payment.amount_cents,
        currency=payment.currency,
        metadata=metadata,
    )

    # Parse response based on provider
    if provider == "stripe":
        result = _parse_stripe_response(response)
    elif provider == "square":
        result = _parse_square_response(response)
    elif provider == "braintree":
        result = _parse_braintree_response(response)
    else:
        result = RetryResult(
            success=False,
            provider=provider,
            provider_response=response,
            new_charge_id=None,
            error_code=FailureCode.PROCESSING_ERROR,
            error_message="Unsupported provider",
            retry_timestamp=datetime.utcnow().isoformat() + "Z",
        )

    activity.logger.info(
        f"Retry result: success={result.success}, "
        f"charge_id={result.new_charge_id}, error={result.error_code}"
    )

    return result
