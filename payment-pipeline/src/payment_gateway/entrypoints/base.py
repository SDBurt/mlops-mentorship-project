"""Shared lifespan and configuration for provider-specific gateways."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from payment_gateway.config import settings
from payment_gateway.core.kafka_producer import KafkaProducerManager

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.

    - Start Kafka producer on startup
    - Stop Kafka producer on shutdown
    """
    provider = getattr(app.state, "provider_name", "unknown")
    # Startup
    logger.info("Starting %s Gateway...", provider.title())
    kafka_manager = KafkaProducerManager()
    await kafka_manager.start()
    app.state.kafka = kafka_manager
    logger.info("%s Gateway started successfully", provider.title())

    yield

    # Shutdown
    logger.info("Shutting down %s Gateway...", provider.title())
    await kafka_manager.stop()
    logger.info("%s Gateway shutdown complete", provider.title())


def create_health_endpoint(app: FastAPI, provider_name: str):
    """Add health check endpoint to the app."""

    @app.get("/health")
    async def health_check():
        """Health check endpoint for container orchestration."""
        return {
            "status": "healthy",
            "service": f"{provider_name}-gateway",
            "kafka_configured": bool(settings.kafka_bootstrap_servers),
        }

    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "service": f"{provider_name.title()} Payment Gateway",
            "version": "1.0.0",
            "endpoints": {
                "health": "/health",
                "webhooks": f"/webhooks/{provider_name}/",
            },
        }
