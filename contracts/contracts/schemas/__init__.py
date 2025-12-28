"""
Shared schema definitions for MLOps platform services.

Re-exports all schemas for convenient imports:
    from contracts.schemas import UnifiedPaymentEvent, FraudScoreRequest
"""

from contracts.schemas.payment_event import (
    UnifiedPaymentEvent,
    STRIPE_EVENT_TYPE_MAP,
    SQUARE_EVENT_TYPE_MAP,
    ADYEN_EVENT_TYPE_MAP,
    BRAINTREE_EVENT_TYPE_MAP,
    normalize_event_type,
)
from contracts.schemas.inference import (
    FraudScoreRequest,
    FraudScoreResponse,
    RetryStrategyRequest,
    RetryStrategyResponse,
    ChurnPredictionRequest,
    ChurnPredictionResponse,
    RetryAction,
)
from contracts.schemas.dlq import (
    DLQPayload,
    WebhookResult,
    WebhookStatus,
)
from contracts.schemas.iceberg import (
    PAYMENT_EVENTS_SCHEMA,
    PAYMENT_EVENTS_QUARANTINE_SCHEMA,
)

__all__ = [
    # Payment event
    "UnifiedPaymentEvent",
    "STRIPE_EVENT_TYPE_MAP",
    "SQUARE_EVENT_TYPE_MAP",
    "ADYEN_EVENT_TYPE_MAP",
    "BRAINTREE_EVENT_TYPE_MAP",
    "normalize_event_type",
    # Inference
    "FraudScoreRequest",
    "FraudScoreResponse",
    "RetryStrategyRequest",
    "RetryStrategyResponse",
    "ChurnPredictionRequest",
    "ChurnPredictionResponse",
    "RetryAction",
    # DLQ
    "DLQPayload",
    "WebhookResult",
    "WebhookStatus",
    # Iceberg
    "PAYMENT_EVENTS_SCHEMA",
    "PAYMENT_EVENTS_QUARANTINE_SCHEMA",
]
