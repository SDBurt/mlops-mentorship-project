"""Square-specific normalizer entrypoint for independent container deployment."""

import asyncio
import logging

from normalizer.config import settings
from normalizer.entrypoints.base import run_normalizer
from normalizer.handlers.square import SquareHandler

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Square-specific topics
SQUARE_TOPICS = [
    "webhooks.square.payment",
    "webhooks.square.refund",
]


def main():
    """Main entry point for Square normalizer."""
    handler = SquareHandler()
    asyncio.run(run_normalizer("square", SQUARE_TOPICS, handler))


if __name__ == "__main__":
    main()
