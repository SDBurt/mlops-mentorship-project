"""Inference service configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Inference service configuration."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8002

    # Model settings
    model_version: str = "mock-v1"

    # Simulated latency (ms)
    min_latency_ms: int = 10
    max_latency_ms: int = 100

    # Logging
    log_level: str = "INFO"

    model_config = {"env_prefix": "INFERENCE_"}


settings = Settings()
