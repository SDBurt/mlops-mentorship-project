# temporal/config.py
"""
Configuration module for Temporal payment workflows.

Environment variables with sensible defaults for local development.
In Docker Compose, these are set via the environment section.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TemporalConfig:
    """Temporal server configuration."""
    host: str = "localhost:7233"
    task_queue: str = "payment-processing"
    namespace: str = "default"


@dataclass(frozen=True)
class KafkaConfig:
    """Kafka configuration."""
    bootstrap_servers: str = "localhost:9092"
    topic_charges: str = "payment_charges"
    topic_refunds: str = "payment_refunds"
    topic_disputes: str = "payment_disputes"


@dataclass(frozen=True)
class Config:
    """Main configuration container."""
    temporal: TemporalConfig
    kafka: KafkaConfig


def load_config() -> Config:
    """
    Load configuration from environment variables with defaults.

    Environment variables:
        TEMPORAL_HOST: Temporal server address (default: localhost:7233)
        TEMPORAL_TASK_QUEUE: Task queue name (default: payment-processing)
        TEMPORAL_NAMESPACE: Temporal namespace (default: default)
        KAFKA_BOOTSTRAP_SERVERS: Kafka bootstrap servers (default: localhost:9092)
    """
    return Config(
        temporal=TemporalConfig(
            host=os.getenv("TEMPORAL_HOST", "localhost:7233"),
            task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "payment-processing"),
            namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
        ),
        kafka=KafkaConfig(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            topic_charges=os.getenv("KAFKA_TOPIC_CHARGES", "payment_charges"),
            topic_refunds=os.getenv("KAFKA_TOPIC_REFUNDS", "payment_refunds"),
            topic_disputes=os.getenv("KAFKA_TOPIC_DISPUTES", "payment_disputes"),
        ),
    )


# Global config instance - loaded once at module import
config = load_config()
