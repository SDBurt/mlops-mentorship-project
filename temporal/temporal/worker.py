# temporal/worker.py
"""
Temporal worker for payment recovery workflows.

Registers the PaymentRecoveryWorkflow and its activities,
then listens on the configured task queue.
"""
import asyncio
import signal
from temporalio.client import Client
from temporalio.worker import Worker

from temporal.config import config
from temporal.workflows.payment_recovery import PaymentRecoveryWorkflow
from temporal.activities import (
    validate_event,
    normalize_event,
    enrich_payment_context,
    predict_retry_strategy,
    execute_provider_retry,
    emit_to_kafka,
)


async def main():
    """Start the Temporal worker with graceful shutdown handling."""
    print(f"Connecting to Temporal at {config.temporal.host}...")
    client = await Client.connect(config.temporal.host)

    worker = Worker(
        client,
        task_queue=config.temporal.task_queue,
        workflows=[PaymentRecoveryWorkflow],
        activities=[
            validate_event,
            normalize_event,
            enrich_payment_context,
            predict_retry_strategy,
            execute_provider_retry,
            emit_to_kafka,
        ],
    )

    # Set up graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler():
        print("\nShutdown signal received, stopping worker...")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    print(f"Worker started, listening on task queue: {config.temporal.task_queue}")
    print(f"Kafka bootstrap servers: {config.kafka.bootstrap_servers}")

    # Run worker until shutdown signal
    async with worker:
        await shutdown_event.wait()

    print("Worker stopped gracefully")


if __name__ == "__main__":
    asyncio.run(main())
