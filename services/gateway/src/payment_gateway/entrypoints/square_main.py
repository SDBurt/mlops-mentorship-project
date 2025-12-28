"""Square-specific gateway entrypoint for independent container deployment."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from payment_gateway.config import settings
from payment_gateway.entrypoints.base import create_health_endpoint, lifespan
from payment_gateway.providers.square.router import router as square_router

app = FastAPI(
    title="Square Payment Gateway",
    description="Webhook gateway for Square payment provider",
    version="1.0.0",
    lifespan=lifespan,
)

# Store provider name for lifespan logging
app.state.provider_name = "square"

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Square router
app.include_router(square_router, prefix="/webhooks/square", tags=["square"])

# Add health check endpoints
create_health_endpoint(app, "square")
