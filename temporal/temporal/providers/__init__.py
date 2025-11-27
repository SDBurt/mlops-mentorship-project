# temporal/providers/__init__.py
"""
Multi-provider payment generation.

Supports Stripe, Square, and Braintree payment schemas with a normalized
output format for provider-agnostic workflow processing.

Usage:
    from temporal.providers import generate_payment, generate_failed_payment, Provider

    # Generate from specific provider
    payment = generate_payment(Provider.STRIPE)

    # Generate from random provider
    payment = generate_payment()  # Random selection

    # Generate failed payment event for recovery workflow
    failed_event = generate_failed_payment()  # Random provider and failure
    failed_event = generate_failed_payment(Provider.STRIPE, "insufficient_funds")
"""
import random
from temporal.providers.base import Provider, NormalizedPayment, FailedPaymentEvent, FailureCode
from temporal.providers.stripe import StripeProvider
from temporal.providers.square import SquareProvider
from temporal.providers.braintree import BraintreeProvider

__all__ = [
    "Provider",
    "NormalizedPayment",
    "FailedPaymentEvent",
    "FailureCode",
    "generate_payment",
    "generate_failed_payment",
    "StripeProvider",
    "SquareProvider",
    "BraintreeProvider",
]

# Provider instances (singleton pattern)
_providers = {
    Provider.STRIPE: StripeProvider(),
    Provider.SQUARE: SquareProvider(),
    Provider.BRAINTREE: BraintreeProvider(),
}

# Weighted distribution for random selection (Stripe dominant)
_provider_weights = [
    (Provider.STRIPE, 60),
    (Provider.SQUARE, 25),
    (Provider.BRAINTREE, 15),
]


def _select_random_provider() -> Provider:
    """Select a random provider using weighted distribution."""
    choices = []
    for p, weight in _provider_weights:
        choices.extend([p] * weight)
    return random.choice(choices)


def generate_payment(provider: Provider | None = None) -> NormalizedPayment:
    """
    Generate a synthetic payment from the specified provider.

    Args:
        provider: Specific provider to use, or None for random selection
                  weighted by market share (60% Stripe, 25% Square, 15% Braintree)

    Returns:
        NormalizedPayment with provider-agnostic schema
    """
    if provider is None:
        provider = _select_random_provider()

    return _providers[provider].generate_payment()


def generate_failed_payment(
    provider: Provider | None = None,
    failure_code: str | None = None,
) -> FailedPaymentEvent:
    """
    Generate a synthetic failed payment event for recovery workflow.

    This simulates receiving a webhook from a payment provider about a failed
    payment that needs recovery attempts.

    Args:
        provider: Specific provider to use, or None for random selection
                  weighted by market share (60% Stripe, 25% Square, 15% Braintree)
        failure_code: Specific failure code to use, or None for random selection
                      based on realistic distribution for the provider

    Returns:
        FailedPaymentEvent ready for PaymentRecoveryWorkflow
    """
    if provider is None:
        provider = _select_random_provider()

    return _providers[provider].generate_failed_payment(failure_code)
