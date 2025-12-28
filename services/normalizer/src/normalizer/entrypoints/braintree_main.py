"""Braintree-specific normalizer entrypoint for independent container deployment."""

import asyncio
import logging

from normalizer.config import settings
from normalizer.entrypoints.base import run_normalizer
from normalizer.handlers.braintree import BraintreeHandler

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Braintree-specific topics
BRAINTREE_TOPICS = [
    "webhooks.braintree.notification",
]


def main():
    """Main entry point for Braintree normalizer."""
    handler = BraintreeHandler()
    asyncio.run(run_normalizer("braintree", BRAINTREE_TOPICS, handler))


if __name__ == "__main__":
    main()
