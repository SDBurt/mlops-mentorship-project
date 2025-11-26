# temporal/providers/__init__.py
"""
Multi-provider payment generation.

Supports Stripe, Square, and Braintree payment schemas with a normalized
output format for provider-agnostic workflow processing.

Usage:
    from temporal.providers import generate_payment, Provider

    # Generate from specific provider
    payment = generate_payment(Provider.STRIPE)

    # Generate from random provider
    payment = generate_payment()  # Random selection
"""
import random
from temporal.providers.base import Provider, NormalizedPayment
from temporal.providers.stripe import StripeProvider
from temporal.providers.square import SquareProvider
from temporal.providers.braintree import BraintreeProvider

__all__ = [
    "Provider",
    "NormalizedPayment",
    "generate_payment",
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
        # Weighted random selection
        choices = []
        for p, weight in _provider_weights:
            choices.extend([p] * weight)
        provider = random.choice(choices)

    return _providers[provider].generate_payment()
