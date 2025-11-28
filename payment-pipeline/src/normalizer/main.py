"""Main entry point for the normalizer service."""

import asyncio
import logging
import signal
import sys
from typing import NoReturn

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

from .config import settings
from .handlers.stripe import StripeHandler

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class NormalizerService:
    """Kafka consumer service that validates and normalizes payment events."""

    def __init__(self):
        self.consumer: AIOKafkaConsumer | None = None
        self.producer: AIOKafkaProducer | None = None
        self.stripe_handler = StripeHandler()
        self._shutdown_event = asyncio.Event()
        self._stats = {
            "processed": 0,
            "valid": 0,
            "invalid": 0,
        }

    async def start(self) -> None:
        """Start the consumer and producer."""
        logger.info("Starting normalizer service...")
        logger.info("Input topics: %s", settings.input_topics_list)
        logger.info("Output topic: %s", settings.output_topic)
        logger.info("DLQ topic: %s", settings.dlq_topic)

        # Create consumer with retry
        self.consumer = await self._create_consumer_with_retry()

        # Create producer with retry
        self.producer = await self._create_producer_with_retry()

        logger.info("Normalizer service started successfully")

    async def _create_consumer_with_retry(
        self,
        max_retries: int = 10,
        retry_delay: float = 2.0,
    ) -> AIOKafkaConsumer:
        """Create Kafka consumer with retry logic."""
        for attempt in range(1, max_retries + 1):
            try:
                consumer = AIOKafkaConsumer(
                    *settings.input_topics_list,
                    bootstrap_servers=settings.kafka_bootstrap_servers,
                    group_id=settings.kafka_consumer_group,
                    auto_offset_reset=settings.kafka_auto_offset_reset,
                    enable_auto_commit=True,
                )
                await consumer.start()
                logger.info("Kafka consumer connected (attempt %d)", attempt)
                return consumer
            except KafkaConnectionError as e:
                if attempt == max_retries:
                    logger.error("Failed to connect to Kafka after %d attempts", max_retries)
                    raise
                logger.warning(
                    "Kafka connection failed (attempt %d/%d): %s",
                    attempt,
                    max_retries,
                    e,
                )
                await asyncio.sleep(retry_delay * attempt)

        raise RuntimeError("Failed to create consumer")

    async def _create_producer_with_retry(
        self,
        max_retries: int = 10,
        retry_delay: float = 2.0,
    ) -> AIOKafkaProducer:
        """Create Kafka producer with retry logic."""
        for attempt in range(1, max_retries + 1):
            try:
                producer = AIOKafkaProducer(
                    bootstrap_servers=settings.kafka_bootstrap_servers,
                    acks="all",
                    enable_idempotence=True,
                    compression_type="gzip",
                )
                await producer.start()
                logger.info("Kafka producer connected (attempt %d)", attempt)
                return producer
            except KafkaConnectionError as e:
                if attempt == max_retries:
                    logger.error("Failed to connect to Kafka after %d attempts", max_retries)
                    raise
                logger.warning(
                    "Kafka connection failed (attempt %d/%d): %s",
                    attempt,
                    max_retries,
                    e,
                )
                await asyncio.sleep(retry_delay * attempt)

        raise RuntimeError("Failed to create producer")

    async def stop(self) -> None:
        """Stop the consumer and producer."""
        logger.info("Stopping normalizer service...")

        if self.consumer:
            await self.consumer.stop()
            logger.info("Consumer stopped")

        if self.producer:
            await self.producer.stop()
            logger.info("Producer stopped")

        logger.info(
            "Service stopped. Stats: processed=%d, valid=%d, invalid=%d",
            self._stats["processed"],
            self._stats["valid"],
            self._stats["invalid"],
        )

    async def run(self) -> None:
        """Run the main processing loop."""
        if not self.consumer or not self.producer:
            raise RuntimeError("Service not started")

        logger.info("Starting message processing loop...")

        try:
            async for msg in self.consumer:
                if self._shutdown_event.is_set():
                    break

                await self._process_message(msg)
        except asyncio.CancelledError:
            logger.info("Processing loop cancelled")
        except Exception as e:
            logger.exception("Error in processing loop: %s", e)
            raise

    async def _process_message(self, msg) -> None:
        """Process a single Kafka message."""
        self._stats["processed"] += 1

        # Determine handler based on topic
        handler = self._get_handler(msg.topic)
        if not handler:
            logger.warning("No handler for topic: %s", msg.topic)
            return

        # Process the message
        result = handler.process(
            raw_value=msg.value,
            source_topic=msg.topic,
            partition=msg.partition,
            offset=msg.offset,
        )

        # Send to appropriate output topic
        if result.is_valid and result.normalized_payload:
            await self.producer.send_and_wait(
                settings.output_topic,
                value=result.normalized_payload,
                key=result.event_id.encode("utf-8") if result.event_id else None,
            )
            self._stats["valid"] += 1
            logger.debug("Sent normalized event to %s", settings.output_topic)
        elif result.dlq_payload:
            await self.producer.send_and_wait(
                settings.dlq_topic,
                value=result.dlq_payload,
                key=result.event_id.encode("utf-8") if result.event_id else None,
            )
            self._stats["invalid"] += 1
            logger.debug("Sent invalid event to %s", settings.dlq_topic)

        # Log progress periodically
        if self._stats["processed"] % 100 == 0:
            logger.info(
                "Progress: processed=%d, valid=%d, invalid=%d",
                self._stats["processed"],
                self._stats["valid"],
                self._stats["invalid"],
            )

    def _get_handler(self, topic: str):
        """Get the appropriate handler for a topic."""
        if "stripe" in topic:
            return self.stripe_handler
        # Add more handlers here as needed
        return None

    def request_shutdown(self) -> None:
        """Request graceful shutdown."""
        logger.info("Shutdown requested")
        self._shutdown_event.set()


async def main() -> NoReturn:
    """Main entry point."""
    service = NormalizerService()

    # Set up signal handlers
    loop = asyncio.get_running_loop()

    def signal_handler():
        service.request_shutdown()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await service.start()
        await service.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)
    finally:
        await service.stop()

    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
