"""Base transformer and unified payment event schema.

This module re-exports schemas from the contracts package for backwards compatibility.
The canonical definitions are now in contracts/schemas/payment_event.py.
"""

# Re-export from contracts for backwards compatibility
from contracts.schemas.payment_event import (
    UnifiedPaymentEvent,
    STRIPE_EVENT_TYPE_MAP,
    SQUARE_EVENT_TYPE_MAP,
    ADYEN_EVENT_TYPE_MAP,
    BRAINTREE_EVENT_TYPE_MAP,
    normalize_event_type,
)

__all__ = [
    "UnifiedPaymentEvent",
    "STRIPE_EVENT_TYPE_MAP",
    "SQUARE_EVENT_TYPE_MAP",
    "ADYEN_EVENT_TYPE_MAP",
    "BRAINTREE_EVENT_TYPE_MAP",
    "normalize_event_type",
]
