"""Inference service FastAPI application."""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

import mlflow
from fastapi import FastAPI
from feast import FeatureStore

from .config import settings
from .routes import fraud, retry, churn, recovery

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global state for models and feature store
# In production, you might use a dependency injection pattern
models: Dict[str, Any] = {}
feature_store: FeatureStore = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for loading models and feature store."""
    global feature_store
    
    # Initialize MLflow
    logger.info(f"Setting MLflow tracking URI to: {settings.mlflow_tracking_uri}")
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    
    # Load models
    model_names = ["fraud-detection", "churn-prediction"]
    for name in model_names:
        try:
            # Load latest production model from registry
            model_uri = f"models:/{name}/Production"
            logger.info(f"Loading model: {model_uri}")
            models[name] = mlflow.sklearn.load_model(model_uri)
            logger.info(f"Successfully loaded model: {name}")
        except Exception as e:
            logger.error(f"Failed to load model {name}: {e}. Falling back to mock logic.")
            models[name] = None
            
    # Initialize Feast FeatureStore
    try:
        # In Docker environment, FEAST_REPO_PATH should point to the directory 
        # containing feature_store.yaml
        feature_store = FeatureStore(repo_path=settings.feast_repo_path)
        logger.info(f"Feast FeatureStore initialized from {settings.feast_repo_path}")
    except Exception as e:
        logger.error(f"Failed to initialize Feast FeatureStore: {e}")
        feature_store = None
        
    yield
    
    # Cleanup
    models.clear()
    if feature_store:
        feature_store.close()


app = FastAPI(
    title="Payment Inference Service",
    description="ML inference service for fraud scoring, retry strategy, churn prediction, and payment recovery",
    version="1.0.0",
    lifespan=lifespan,
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
