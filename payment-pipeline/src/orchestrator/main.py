"""Orchestrator service main entrypoint."""

import asyncio
import logging
import sys

from temporalio.client import Client
from temporalio.worker import Worker

from .config import settings
from .consumer import KafkaTemporalBridge, setup_signal_handlers
from .workflows.payment_event import PaymentEventWorkflow
from .workflows.dlq_review import DLQReviewWorkflow
from .activities import (
    validate_business_rules,
    get_fraud_score,
    get_retry_strategy,
    get_churn_prediction,
    persist_to_postgres,
    persist_quarantine_to_postgres,
)


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def run_worker(client: Client) -> None:
    """
    Run the Temporal worker.

    The worker executes workflows and activities for the payment-processing
    task queue.

    Args:
        client: Connected Temporal client
    """
    logger.info(f"Starting Temporal worker on task queue: {settings.temporal_task_queue}")

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[PaymentEventWorkflow, DLQReviewWorkflow],
        activities=[
            validate_business_rules,
            get_fraud_score,
            get_retry_strategy,
            get_churn_prediction,
            persist_to_postgres,
            persist_quarantine_to_postgres,
        ],
    )

    await worker.run()


async def run_consumer(client: Client) -> None:
    """
    Run the Kafka-Temporal bridge consumer.

    The consumer reads from Kafka and starts Temporal workflows for each event.

    Args:
        client: Connected Temporal client
    """
    bridge = KafkaTemporalBridge(client)

    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    setup_signal_handlers(bridge, loop)

    try:
        await bridge.start()
        await bridge.run()
    finally:
        await bridge.stop()


async def main() -> None:
    """Main orchestrator entrypoint."""
    logger.info("=" * 60)
    logger.info("Starting Payment Orchestrator Service")
    logger.info("=" * 60)
    logger.info(f"Temporal host: {settings.temporal_host}")
    logger.info(f"Temporal namespace: {settings.temporal_namespace}")
    logger.info(f"Task queue: {settings.temporal_task_queue}")
    logger.info(f"Kafka servers: {settings.kafka_bootstrap_servers}")
    logger.info(f"Input topic: {settings.input_topic}")
    logger.info(f"DLQ topic: {settings.dlq_topic}")
    logger.info("=" * 60)

    # Connect to Temporal with proper error handling and cleanup
    client = None
    try:
        logger.info("Connecting to Temporal...")
        client = await Client.connect(
            settings.temporal_host,
            namespace=settings.temporal_namespace,
        )
        logger.info("Connected to Temporal successfully")

        # Run worker and consumer concurrently
        # The worker executes workflows/activities, the consumer triggers them
        logger.info("Starting worker and consumer...")

        await asyncio.gather(
            run_worker(client),
            run_consumer(client),
        )
    except asyncio.CancelledError:
        logger.info("Service cancelled, shutting down...")
    except Exception as e:
        logger.exception(f"Service error: {e}")
        raise
    finally:
        if client:
            await client.close()
            logger.info("Temporal client closed")
        logger.info("Payment Orchestrator Service stopped")


if __name__ == "__main__":
    asyncio.run(main())
