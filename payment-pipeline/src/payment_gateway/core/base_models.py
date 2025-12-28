"""Base models shared across all payment providers.

This module re-exports schemas from the contracts package for backwards compatibility.
The canonical definitions are now in contracts/schemas/dlq.py.
"""

# Re-export from contracts for backwards compatibility
from contracts.schemas.dlq import (
    DLQPayload,
    WebhookResult,
    WebhookStatus,
)

__all__ = [
    "DLQPayload",
    "WebhookResult",
    "WebhookStatus",
]
