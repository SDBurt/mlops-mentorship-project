"""Inference service FastAPI application."""

import logging

from fastapi import FastAPI

from .config import settings
from .routes import fraud, retry, churn, recovery

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Payment Inference Service",
    description="ML inference service for fraud scoring, retry strategy, churn prediction, and payment recovery",
    version="1.0.0",
)

app.include_router(fraud.router, prefix="/fraud", tags=["fraud"])
app.include_router(retry.router, prefix="/retry", tags=["retry"])
app.include_router(churn.router, prefix="/churn", tags=["churn"])
app.include_router(recovery.router, prefix="/recovery", tags=["recovery"])


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "inference-service",
        "model_version": settings.model_version,
    }


@app.get("/")
async def root() -> dict:
    """Root endpoint with service info."""
    return {
        "service": "Payment Inference Service",
        "version": "1.0.0",
        "endpoints": {
            "fraud_score": "/fraud/score",
            "retry_strategy": "/retry/strategy",
            "churn_prediction": "/churn/predict",
            "payment_recovery": "/recovery/recommend",
            "health": "/health",
        },
    }
