"""Stripe-specific normalizer entrypoint for independent container deployment."""

import asyncio
import logging

from transformer.config import settings
from transformer.entrypoints.base import run_normalizer
from transformer.handlers.stripe import StripeHandler

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Stripe-specific topics
STRIPE_TOPICS = [
    "webhooks.stripe.payment_intent",
    "webhooks.stripe.charge",
    "webhooks.stripe.refund",
]


def main():
    """Main entry point for Stripe normalizer."""
    handler = StripeHandler()
    asyncio.run(run_normalizer("stripe", STRIPE_TOPICS, handler))


if __name__ == "__main__":
    main()
