"""Braintree-specific gateway entrypoint for independent container deployment."""

import logging
from contextlib import asynccontextmanager

import braintree
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from payment_gateway.config import settings
from payment_gateway.core.kafka_producer import KafkaProducerManager
from payment_gateway.providers.braintree.router import router as braintree_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle for Braintree gateway.

    - Configure Braintree SDK on startup
    - Start Kafka producer on startup
    - Stop Kafka producer on shutdown
    """
    # Startup
    logger.info("Starting Braintree Gateway...")

    # Configure Braintree SDK
    environment = (
        braintree.Environment.Production
        if settings.braintree_environment == "production"
        else braintree.Environment.Sandbox
    )

    gateway = braintree.BraintreeGateway(
        braintree.Configuration(
            environment=environment,
            merchant_id=settings.braintree_merchant_id,
            public_key=settings.braintree_public_key,
            private_key=settings.braintree_private_key,
        )
    )
    app.state.braintree_gateway = gateway
    logger.info("Braintree SDK configured for %s environment", settings.braintree_environment)

    # Start Kafka
    kafka_manager = KafkaProducerManager()
    await kafka_manager.start()
    app.state.kafka = kafka_manager
    logger.info("Braintree Gateway started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Braintree Gateway...")
    await kafka_manager.stop()
    logger.info("Braintree Gateway shutdown complete")


app = FastAPI(
    title="Braintree Payment Gateway",
    description="Webhook gateway for Braintree payment provider",
    version="1.0.0",
    lifespan=lifespan,
)

# Store provider name for logging
app.state.provider_name = "braintree"

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Braintree router
app.include_router(braintree_router, prefix="/webhooks/braintree", tags=["braintree"])


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {
        "status": "healthy",
        "service": "braintree-gateway",
        "kafka_configured": bool(settings.kafka_bootstrap_servers),
        "braintree_configured": bool(settings.braintree_merchant_id),
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Braintree Payment Gateway",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "webhooks": "/webhooks/braintree/",
        },
    }
