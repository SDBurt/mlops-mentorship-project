# temporal/activities/kafka_emitter.py
"""
Kafka emitter activity for payment events.

Uses dependency injection pattern for the producer to enable:
- Efficient connection reuse (no per-event overhead)
- Easy testing with mock producers
- Configurable bootstrap servers via environment
"""
from typing import Protocol
import json

from temporalio import activity
from aiokafka import AIOKafkaProducer

from temporal.config import config


class KafkaProducerProtocol(Protocol):
    """Protocol for Kafka producer dependency injection."""

    async def send_and_wait(self, topic: str, value: bytes) -> None:
        """Send a message to a Kafka topic."""
        ...


class KafkaProducerWrapper:
    """
    Wrapper around AIOKafkaProducer with lazy initialization.

    Creates the producer on first use and reuses it for subsequent calls.
    This avoids the overhead of creating a new connection per event.
    """

    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self._producer: AIOKafkaProducer | None = None

    async def _get_producer(self) -> AIOKafkaProducer:
        """Get or create the producer instance."""
        if self._producer is None:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8")
            )
            await self._producer.start()
        return self._producer

    async def send_and_wait(self, topic: str, value: dict) -> None:
        """Send a message to a Kafka topic."""
        producer = await self._get_producer()
        await producer.send_and_wait(topic, value)

    async def close(self) -> None:
        """Close the producer connection."""
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None


# Module-level producer instance for connection reuse
_producer_wrapper: KafkaProducerWrapper | None = None


def get_producer() -> KafkaProducerWrapper:
    """Get the shared Kafka producer instance."""
    global _producer_wrapper
    if _producer_wrapper is None:
        _producer_wrapper = KafkaProducerWrapper(config.kafka.bootstrap_servers)
    return _producer_wrapper


def set_producer(producer: KafkaProducerWrapper) -> None:
    """
    Set a custom producer instance (for testing).

    Example:
        mock_producer = MockKafkaProducer()
        set_producer(mock_producer)
    """
    global _producer_wrapper
    _producer_wrapper = producer


@activity.defn
async def emit_to_kafka(topic: str, event: dict) -> None:
    """
    Emit a payment event to Kafka for downstream processing.

    Args:
        topic: Kafka topic to send to (e.g., "payment_charges")
        event: Event payload to send

    The producer is shared across activity invocations to avoid
    connection overhead. Use set_producer() to inject a mock for testing.
    """
    activity.logger.info(f"Emitting to {topic}: {event.get('type')}")

    producer = get_producer()
    await producer.send_and_wait(topic, event)

    activity.logger.debug(f"Successfully emitted event {event.get('event_id')} to {topic}")
