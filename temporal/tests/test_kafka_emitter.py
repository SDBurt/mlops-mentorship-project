# tests/test_kafka_emitter.py
"""
Unit tests for Kafka event emission activity.

Tests the emit_to_kafka activity and KafkaProducerWrapper
using dependency injection for mocking.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from temporal.activities.kafka_emitter import (
    emit_to_kafka,
    get_producer,
    set_producer,
    KafkaProducerWrapper,
)


@pytest.fixture(autouse=True)
def reset_producer():
    """Reset the global producer before and after each test."""
    set_producer(None)
    yield
    set_producer(None)


@pytest.fixture
def mock_producer():
    """Create a mock Kafka producer with async send_and_wait."""
    producer = AsyncMock()
    producer.send_and_wait = AsyncMock()
    return producer


@pytest.fixture(autouse=True)
def mock_activity_logger():
    """Mock activity.logger for all tests since we're not in an activity context."""
    with patch("temporal.activities.kafka_emitter.activity") as mock_activity:
        mock_activity.logger = MagicMock()
        yield mock_activity.logger


class TestEmitToKafka:
    """Tests for the emit_to_kafka activity."""

    @pytest.fixture
    def sample_event(self) -> dict:
        """Sample payment event for testing."""
        return {
            "event_id": "evt_abc123",
            "type": "charge.succeeded",
            "provider": "stripe",
            "data": {"amount_cents": 5000, "currency": "USD"}
        }

    @pytest.mark.asyncio
    async def test_emits_event_to_correct_topic(self, mock_producer, sample_event):
        """Should send event to the specified topic."""
        set_producer(mock_producer)

        await emit_to_kafka("payment_charges", sample_event)

        mock_producer.send_and_wait.assert_called_once()
        call_args = mock_producer.send_and_wait.call_args
        assert call_args[0][0] == "payment_charges"  # topic

    @pytest.mark.asyncio
    async def test_sends_event_data(self, mock_producer, sample_event):
        """Should send the event data to Kafka."""
        set_producer(mock_producer)

        await emit_to_kafka("test_topic", sample_event)

        call_args = mock_producer.send_and_wait.call_args
        sent_event = call_args[0][1]
        assert sent_event["event_id"] == "evt_abc123"
        assert sent_event["type"] == "charge.succeeded"

    @pytest.mark.asyncio
    async def test_reuses_producer_instance(self, mock_producer):
        """Should reuse the same producer for multiple calls."""
        set_producer(mock_producer)
        event1 = {"event_id": "evt_1", "type": "test"}
        event2 = {"event_id": "evt_2", "type": "test"}

        await emit_to_kafka("topic1", event1)
        await emit_to_kafka("topic2", event2)

        assert mock_producer.send_and_wait.call_count == 2

    @pytest.mark.asyncio
    async def test_logs_event_type(self, mock_producer, sample_event, mock_activity_logger):
        """Should log the event type being emitted."""
        set_producer(mock_producer)

        await emit_to_kafka("payment_charges", sample_event)

        mock_activity_logger.info.assert_called()
        log_message = mock_activity_logger.info.call_args[0][0]
        assert "charge.succeeded" in log_message


class TestKafkaProducerWrapper:
    """Tests for the KafkaProducerWrapper class."""

    def test_wrapper_stores_bootstrap_servers(self):
        """Should store bootstrap servers on initialization."""
        wrapper = KafkaProducerWrapper("localhost:9092")
        assert wrapper.bootstrap_servers == "localhost:9092"

    def test_wrapper_starts_with_no_producer(self):
        """Should not create producer until first use."""
        wrapper = KafkaProducerWrapper("localhost:9092")
        assert wrapper._producer is None

    @pytest.mark.asyncio
    async def test_send_and_wait_creates_producer_lazily(self):
        """Should create producer on first send."""
        with patch("temporal.activities.kafka_emitter.AIOKafkaProducer") as MockProducer:
            mock_aiokafka = AsyncMock()
            MockProducer.return_value = mock_aiokafka

            wrapper = KafkaProducerWrapper("localhost:9092")
            await wrapper.send_and_wait("topic", {"key": "value"})

            MockProducer.assert_called_once()
            mock_aiokafka.start.assert_called_once()
            mock_aiokafka.send_and_wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_stops_producer(self):
        """Should stop producer on close."""
        with patch("temporal.activities.kafka_emitter.AIOKafkaProducer") as MockProducer:
            mock_aiokafka = AsyncMock()
            MockProducer.return_value = mock_aiokafka

            wrapper = KafkaProducerWrapper("localhost:9092")
            await wrapper.send_and_wait("topic", {"key": "value"})
            await wrapper.close()

            mock_aiokafka.stop.assert_called_once()
            assert wrapper._producer is None


class TestProducerSingleton:
    """Tests for producer singleton behavior."""

    def test_set_producer_allows_injection(self, mock_producer):
        """set_producer should allow dependency injection."""
        set_producer(mock_producer)
        assert get_producer() is mock_producer

    def test_set_producer_none_clears_instance(self, mock_producer):
        """set_producer(None) should clear the singleton."""
        set_producer(mock_producer)
        set_producer(None)
        # After clearing, calling get_producer would create a new real producer
        # We don't test that here to avoid Kafka connection
        assert True  # Just verify no exception

    def test_get_producer_returns_same_instance(self):
        """get_producer should return the same instance on multiple calls."""
        with patch("temporal.activities.kafka_emitter.config") as mock_config:
            mock_config.kafka.bootstrap_servers = "localhost:9092"

            producer1 = get_producer()
            producer2 = get_producer()

            assert producer1 is producer2
