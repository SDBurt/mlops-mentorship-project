"""FastAPI application entry point for the Payment Gateway."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from payment_gateway.config import settings
from payment_gateway.core.kafka_producer import KafkaProducerManager
from payment_gateway.providers.stripe.router import router as stripe_router

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
    # Startup
    logger.info("Starting Payment Gateway...")
    kafka_manager = KafkaProducerManager()
    await kafka_manager.start()
    app.state.kafka = kafka_manager
    logger.info("Payment Gateway started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Payment Gateway...")
    await kafka_manager.stop()
    logger.info("Payment Gateway shutdown complete")


app = FastAPI(
    title="Payment Gateway",
    description="Webhook gateway for payment providers (Stripe, Square, etc.)",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware (configure as needed for your environment)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include provider routers
app.include_router(stripe_router, prefix="/webhooks/stripe", tags=["stripe"])


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {
        "status": "healthy",
        "service": "payment-gateway",
        "kafka_configured": bool(settings.kafka_bootstrap_servers),
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Payment Gateway",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "stripe_webhooks": "/webhooks/stripe/",
        },
    }
