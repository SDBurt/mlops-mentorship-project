"""Data models for inference service requests and responses.

This module re-exports schemas from the contracts package for backwards compatibility.
The canonical definitions are now in contracts/schemas/inference.py.
"""

# Re-export from contracts for backwards compatibility
from contracts.schemas.inference import (
    FraudScoreRequest,
    FraudScoreResponse,
    RetryAction,
    RetryStrategyRequest,
    RetryStrategyResponse,
)

__all__ = [
    "FraudScoreRequest",
    "FraudScoreResponse",
    "RetryAction",
    "RetryStrategyRequest",
    "RetryStrategyResponse",
]
