"""Stripe-specific gateway entrypoint for independent container deployment."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from payment_gateway.config import settings
from payment_gateway.entrypoints.base import create_health_endpoint, lifespan
from payment_gateway.providers.stripe.router import router as stripe_router

app = FastAPI(
    title="Stripe Payment Gateway",
    description="Webhook gateway for Stripe payment provider",
    version="1.0.0",
    lifespan=lifespan,
)

# Store provider name for lifespan logging
app.state.provider_name = "stripe"

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Stripe router
app.include_router(stripe_router, prefix="/webhooks/stripe", tags=["stripe"])

# Add health check endpoints
create_health_endpoint(app, "stripe")
