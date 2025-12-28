"""Orchestrator configuration using Pydantic Settings."""

from urllib.parse import quote_plus

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Orchestrator service configuration."""

    # Kafka settings
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "orchestrator-group"
    kafka_auto_offset_reset: str = "earliest"

    # Input topics
    input_topic: str = "payments.normalized"
    dlq_topic: str = "payments.validation.dlq"

    # Temporal settings
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "payment-processing"

    # Inference service settings
    inference_service_url: str = "http://localhost:8002"
    inference_timeout_seconds: float = 30.0

    # Postgres settings (for payment event storage)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "payments"
    postgres_password: str = "payments"
    postgres_db: str = "payments"

    @property
    def postgres_dsn(self) -> str:
        """Build Postgres connection string with URL-encoded credentials."""
        encoded_user = quote_plus(self.postgres_user)
        encoded_password = quote_plus(self.postgres_password)
        return f"postgresql://{encoded_user}:{encoded_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    # Processing settings
    batch_size: int = 100

    # Logging
    log_level: str = "INFO"

    model_config = {"env_prefix": "ORCHESTRATOR_"}


settings = Settings()
