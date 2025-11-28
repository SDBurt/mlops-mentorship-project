"""Configuration management using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Kafka Configuration
    kafka_bootstrap_servers: str = "kafka-broker:29092"
    kafka_topic_prefix: str = "webhooks"
    kafka_dlq_topic: str = "webhooks.dlq"
    kafka_acks: str = "all"
    kafka_compression_type: str = "gzip"
    kafka_connection_retries: int = 10
    kafka_retry_delay: float = 2.0  # Initial delay in seconds
    kafka_retry_max_delay: float = 30.0  # Max delay between retries

    # Stripe Configuration
    stripe_webhook_secret: str = ""
    stripe_signature_tolerance: int = 300  # seconds

    # Application
    debug: bool = False
    log_level: str = "INFO"

    @property
    def stripe_topic_payment_intent(self) -> str:
        return f"{self.kafka_topic_prefix}.stripe.payment_intent"

    @property
    def stripe_topic_charge(self) -> str:
        return f"{self.kafka_topic_prefix}.stripe.charge"

    @property
    def stripe_topic_refund(self) -> str:
        return f"{self.kafka_topic_prefix}.stripe.refund"


settings = Settings()
