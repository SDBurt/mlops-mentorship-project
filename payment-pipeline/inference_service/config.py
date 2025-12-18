"""Inference service configuration."""

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Inference service configuration."""

    # Server settings
    # Defaults to 0.0.0.0 for Docker containers, override with INFERENCE_HOST if needed
    host: str = "0.0.0.0"
    port: int = 8002

    # Model settings
    model_version: str = "mock-v1"

    # MLOps settings
    feast_repo_path: str = "/app/feature_repo"
    mlflow_tracking_uri: str = "http://mlflow-server:5000"
    feast_redis_host: str = "feast-redis"
    feast_redis_port: int = 6379

    # Simulated latency (ms)
    min_latency_ms: int = 10
    max_latency_ms: int = 100

    # Logging
    log_level: str = "INFO"

    model_config = {"env_prefix": "INFERENCE_"}

    @field_validator("max_latency_ms")
    @classmethod
    def validate_latency_range(cls, v, info):
        """Ensure max_latency_ms > min_latency_ms."""
        min_val = info.data.get("min_latency_ms", 0)
        if v <= min_val:
            raise ValueError(f"max_latency_ms ({v}) must be > min_latency_ms ({min_val})")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log_level is a valid Python logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()


settings = Settings()
