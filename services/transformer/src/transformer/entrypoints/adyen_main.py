"""Adyen-specific normalizer entrypoint for independent container deployment."""

import asyncio
import logging

from transformer.config import settings
from transformer.entrypoints.base import run_normalizer
from transformer.handlers.adyen import AdyenHandler

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Adyen-specific topics
ADYEN_TOPICS = [
    "webhooks.adyen.notification",
]


def main():
    """Main entry point for Adyen normalizer."""
    handler = AdyenHandler()
    asyncio.run(run_normalizer("adyen", ADYEN_TOPICS, handler))


if __name__ == "__main__":
    main()
