"""Normalizer configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Normalizer service configuration."""

    # Kafka settings
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "normalizer-group"
    kafka_auto_offset_reset: str = "earliest"

    # Input topics (comma-separated)
    input_topics: str = (
        "webhooks.stripe.payment_intent,"
        "webhooks.stripe.charge,"
        "webhooks.stripe.refund,"
        "webhooks.square.payment,"
        "webhooks.square.refund,"
        "webhooks.adyen.notification,"
        "webhooks.braintree.notification"
    )

    # Output topics
    output_topic: str = "payments.normalized"
    dlq_topic: str = "payments.validation.dlq"

    # Processing settings
    batch_size: int = 100
    batch_timeout_ms: int = 1000

    # Logging
    log_level: str = "INFO"

    @property
    def input_topics_list(self) -> list[str]:
        """Parse input topics from comma-separated string."""
        return [t.strip() for t in self.input_topics.split(",") if t.strip()]

    model_config = {"env_prefix": "NORMALIZER_"}


settings = Settings()
