"""Adyen-specific gateway entrypoint for independent container deployment."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from payment_gateway.config import settings
from payment_gateway.entrypoints.base import create_health_endpoint, lifespan
from payment_gateway.providers.adyen.router import router as adyen_router

app = FastAPI(
    title="Adyen Payment Gateway",
    description="Webhook gateway for Adyen payment provider",
    version="1.0.0",
    lifespan=lifespan,
)

# Store provider name for lifespan logging
app.state.provider_name = "adyen"

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Adyen router
app.include_router(adyen_router, prefix="/webhooks/adyen", tags=["adyen"])

# Add health check endpoints
create_health_endpoint(app, "adyen")
