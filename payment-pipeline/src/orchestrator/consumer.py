"""Kafka-Temporal bridge consumer."""

import asyncio
import json
import logging
import signal
from typing import Any

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError
from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy

from .config import settings
from .workflows.payment_event import PaymentEventWorkflow
from .workflows.dlq_review import DLQReviewWorkflow

logger = logging.getLogger(__name__)


class KafkaTemporalBridge:
    """
    Bridges Kafka events to Temporal workflows.

    This consumer reads from Kafka topics (normalized events and DLQ)
    and starts Temporal workflows for each event. It uses event_id as
    the workflow ID to ensure idempotency - duplicate events will not
    create duplicate workflows.
    """

    def __init__(self, temporal_client: Client):
        """
        Initialize the bridge.

        Args:
            temporal_client: Connected Temporal client
        """
        self.temporal_client = temporal_client
        self.consumer: AIOKafkaConsumer | None = None
        self._shutdown_event = asyncio.Event()
        self._stats = {
            "consumed": 0,
            "workflows_started": 0,
            "duplicates_skipped": 0,
            "errors": 0,
            "dlq_workflows": 0,
        }

    async def start(self) -> None:
        """Initialize and start the Kafka consumer."""
        logger.info("Starting Kafka-Temporal bridge...")
        self.consumer = await self._create_consumer_with_retry()
        logger.info("Kafka-Temporal bridge started successfully")

    async def _create_consumer_with_retry(
        self,
        max_retries: int = 10,
        retry_delay: float = 2.0,
    ) -> AIOKafkaConsumer:
        """
        Create Kafka consumer with exponential backoff retry.

        Args:
            max_retries: Maximum number of connection attempts
            retry_delay: Initial delay between retries (doubles each attempt)

        Returns:
            Connected AIOKafkaConsumer

        Raises:
            RuntimeError: If connection fails after all retries
        """
        topics = [settings.input_topic, settings.dlq_topic]

        for attempt in range(1, max_retries + 1):
            try:
                consumer = AIOKafkaConsumer(
                    *topics,
                    bootstrap_servers=settings.kafka_bootstrap_servers,
                    group_id=settings.kafka_consumer_group,
                    auto_offset_reset=settings.kafka_auto_offset_reset,
                    enable_auto_commit=False,  # Manual commit for at-least-once
                    max_poll_records=settings.batch_size,
                    session_timeout_ms=30000,
                    heartbeat_interval_ms=10000,
                )
                await consumer.start()
                logger.info(
                    f"Kafka consumer connected (attempt {attempt}), "
                    f"subscribed to: {topics}"
                )
                return consumer

            except KafkaConnectionError as e:
                if attempt == max_retries:
                    logger.error(f"Failed to connect to Kafka after {max_retries} attempts")
                    raise RuntimeError(f"Kafka connection failed: {e}")

                delay = min(retry_delay * (2 ** (attempt - 1)), 60)  # Cap at 60s
                logger.warning(
                    f"Kafka connection failed (attempt {attempt}/{max_retries}): {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)

        raise RuntimeError("Failed to create Kafka consumer")

    async def run(self) -> None:
        """
        Main processing loop.

        Consumes messages from Kafka and starts Temporal workflows.
        Commits offsets only after successful workflow start to ensure at-least-once delivery.
        """
        if not self.consumer:
            raise RuntimeError("Consumer not started. Call start() first.")

        logger.info("Starting message consumption loop...")

        try:
            async for msg in self.consumer:
                if self._shutdown_event.is_set():
                    logger.info("Shutdown signal received, stopping consumption")
                    break

                success = await self._process_with_retry(msg)

                # Only commit offset on confirmed success
                if success:
                    await self.consumer.commit()
                # If not success, message will be redelivered by Kafka

                # Log progress periodically
                if self._stats["consumed"] % 100 == 0:
                    logger.info(f"Progress: {self._stats}")

        except asyncio.CancelledError:
            logger.info("Consumer loop cancelled")
        except Exception as e:
            logger.exception(f"Error in consumer loop: {e}")
            raise

    async def _process_with_retry(self, msg: Any, max_retries: int = 5) -> bool:
        """
        Process message with exponential backoff retry.

        Args:
            msg: Kafka message
            max_retries: Maximum retry attempts (default 5)

        Returns:
            True if processing succeeded, False otherwise
        """
        for attempt in range(max_retries):
            try:
                await self._process_message(msg)
                return True
            except json.JSONDecodeError as e:
                # JSON errors are not retryable, skip the message
                logger.error(f"Failed to parse message from {msg.topic}: {e}")
                self._stats["errors"] += 1
                return True  # Commit to skip malformed message
            except Exception as e:
                # Check if it's a duplicate (not an error)
                error_str = str(e).lower()
                if "already started" in error_str or "already exists" in error_str:
                    logger.debug(f"Duplicate workflow, skipping: {e}")
                    self._stats["duplicates_skipped"] += 1
                    return True

                if attempt < max_retries - 1:
                    delay = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s, 4s, 8s
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {msg.topic} "
                        f"partition={msg.partition} offset={msg.offset} after {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Failed after {max_retries} retries for {msg.topic} "
                        f"partition={msg.partition} offset={msg.offset}: {e}"
                    )
                    self._stats["errors"] += 1
                    return False

        return False

    async def _process_message(self, msg: Any) -> None:
        """
        Process a single Kafka message.

        Args:
            msg: Kafka message

        Raises:
            json.JSONDecodeError: If message cannot be parsed
            Exception: If workflow start fails
        """
        self._stats["consumed"] += 1
        topic = msg.topic

        # Parse message value (let JSONDecodeError propagate)
        value = json.loads(msg.value.decode("utf-8"))

        # Determine workflow type based on topic (let exceptions propagate)
        if topic == settings.dlq_topic:
            await self._start_dlq_workflow(value, msg)
        else:
            await self._start_payment_workflow(value, msg)

    async def _start_payment_workflow(self, event_data: dict[str, Any], msg: Any) -> None:
        """
        Start a PaymentEventWorkflow for a normalized payment event.

        Args:
            event_data: Normalized payment event data
            msg: Original Kafka message (for metadata)
        """
        event_id = event_data.get("event_id")
        if not event_id:
            logger.warning(f"Message missing event_id, skipping: partition={msg.partition}, offset={msg.offset}")
            self._stats["errors"] += 1
            return

        # Use event_id as workflow ID for idempotency
        workflow_id = f"payment-{event_id}"

        try:
            await self.temporal_client.start_workflow(
                PaymentEventWorkflow.run,
                event_data,
                id=workflow_id,
                task_queue=settings.temporal_task_queue,
                id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
            )

            self._stats["workflows_started"] += 1
            logger.debug(f"Started workflow {workflow_id}")

        except Exception as e:
            # Check if it's a duplicate (workflow already exists)
            error_str = str(e).lower()
            if "already started" in error_str or "already exists" in error_str:
                self._stats["duplicates_skipped"] += 1
                logger.debug(f"Workflow {workflow_id} already exists, skipping")
            else:
                logger.error(f"Failed to start workflow {workflow_id}: {e}")
                self._stats["errors"] += 1
                raise

    async def _start_dlq_workflow(self, dlq_payload: dict[str, Any], msg: Any) -> None:
        """
        Start a DLQReviewWorkflow for a quarantined event.

        Args:
            dlq_payload: DLQ payload with original event and error details
            msg: Original Kafka message (for metadata)
        """
        event_id = dlq_payload.get("event_id")

        # For DLQ, we might not have a valid event_id, use offset as fallback
        if event_id:
            workflow_id = f"dlq-review-{event_id}"
        else:
            workflow_id = f"dlq-review-{msg.partition}-{msg.offset}"

        # Add Kafka metadata to payload
        dlq_payload["kafka_partition"] = msg.partition
        dlq_payload["kafka_offset"] = msg.offset
        dlq_payload["source_topic"] = msg.topic

        try:
            await self.temporal_client.start_workflow(
                DLQReviewWorkflow.run,
                dlq_payload,
                id=workflow_id,
                task_queue=settings.temporal_task_queue,
                id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
            )

            self._stats["dlq_workflows"] += 1
            logger.debug(f"Started DLQ workflow {workflow_id}")

        except Exception as e:
            error_str = str(e).lower()
            if "already started" in error_str or "already exists" in error_str:
                self._stats["duplicates_skipped"] += 1
                logger.debug(f"DLQ workflow {workflow_id} already exists, skipping")
            else:
                logger.error(f"Failed to start DLQ workflow {workflow_id}: {e}")
                self._stats["errors"] += 1
                raise

    async def stop(self) -> None:
        """Gracefully stop the consumer."""
        logger.info("Stopping Kafka-Temporal bridge...")
        self._shutdown_event.set()

        if self.consumer:
            await self.consumer.stop()

        logger.info(f"Bridge stopped. Final stats: {self._stats}")

    def get_stats(self) -> dict[str, int]:
        """Get current processing statistics."""
        return self._stats.copy()


def setup_signal_handlers(bridge: KafkaTemporalBridge, loop: asyncio.AbstractEventLoop) -> None:
    """
    Set up signal handlers for graceful shutdown.

    Args:
        bridge: KafkaTemporalBridge instance to stop
        loop: Event loop
    """
    def handle_signal(sig: signal.Signals) -> None:
        logger.info(f"Received signal {sig.name}, initiating shutdown...")
        loop.create_task(bridge.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal, sig)
