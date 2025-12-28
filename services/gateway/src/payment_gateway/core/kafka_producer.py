"""Kafka producer manager using AIOKafka."""

import asyncio
import logging
from typing import Any

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

from payment_gateway.config import settings
from payment_gateway.core.base_models import DLQPayload
from payment_gateway.core.exceptions import KafkaPublishError

logger = logging.getLogger(__name__)


class KafkaProducerManager:
    """Manages the AIOKafka producer lifecycle and message publishing."""

    def __init__(self):
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        """Initialize and start the Kafka producer with retry logic."""
        if self._producer is not None:
            return

        delay = settings.kafka_retry_delay
        last_error: Exception | None = None

        for attempt in range(1, settings.kafka_connection_retries + 1):
            try:
                self._producer = AIOKafkaProducer(
                    bootstrap_servers=settings.kafka_bootstrap_servers,
                    acks=settings.kafka_acks,
                    compression_type=settings.kafka_compression_type,
                    enable_idempotence=True,
                    max_batch_size=16384,
                    linger_ms=5,
                )
                await self._producer.start()
                logger.info(
                    "Kafka producer started, connected to %s",
                    settings.kafka_bootstrap_servers,
                )
                return
            except KafkaConnectionError as e:
                last_error = e
                self._producer = None
                if attempt < settings.kafka_connection_retries:
                    logger.warning(
                        "Kafka connection attempt %d/%d failed: %s. Retrying in %.1fs...",
                        attempt,
                        settings.kafka_connection_retries,
                        str(e),
                        delay,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, settings.kafka_retry_max_delay)
                else:
                    logger.error(
                        "Failed to connect to Kafka after %d attempts",
                        settings.kafka_connection_retries,
                    )

        raise KafkaPublishError(
            f"Could not connect to Kafka after {settings.kafka_connection_retries} attempts: {last_error}",
            topic="bootstrap",
        )

    async def stop(self) -> None:
        """Stop and cleanup the Kafka producer."""
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
            logger.info("Kafka producer stopped")

    async def send(
        self,
        topic: str,
        value: bytes,
        key: bytes | None = None,
    ) -> dict[str, Any]:
        """
        Send a message to a Kafka topic.

        Args:
            topic: The Kafka topic to send to
            value: The message value as bytes
            key: Optional message key for partitioning

        Returns:
            dict with topic, partition, and offset

        Raises:
            KafkaPublishError: If publishing fails
        """
        if self._producer is None:
            raise KafkaPublishError("Kafka producer not started", topic=topic)

        try:
            result = await self._producer.send_and_wait(
                topic=topic,
                value=value,
                key=key,
            )
            logger.debug(
                "Published message to %s partition %d offset %d",
                result.topic,
                result.partition,
                result.offset,
            )
            return {
                "topic": result.topic,
                "partition": result.partition,
                "offset": result.offset,
            }
        except Exception as e:
            logger.error("Failed to publish to %s: %s", topic, str(e))
            raise KafkaPublishError(str(e), topic=topic) from e

    async def send_to_dlq(
        self,
        provider: str,
        raw_payload: bytes,
        headers: dict[str, str],
        error_type: str,
        error_message: str,
    ) -> dict[str, Any]:
        """
        Send a failed webhook to the dead letter queue.

        Args:
            provider: Payment provider name
            raw_payload: Original raw payload bytes
            headers: Original request headers
            error_type: Type of error that occurred
            error_message: Detailed error message

        Returns:
            dict with topic, partition, and offset
        """
        dlq_payload = DLQPayload(
            provider=provider,
            raw_payload=raw_payload.decode("utf-8", errors="replace"),
            raw_headers=headers,
            error_type=error_type,
            error_message=error_message,
        )

        return await self.send(
            topic=settings.kafka_dlq_topic,
            value=dlq_payload.model_dump_json().encode("utf-8"),
        )
