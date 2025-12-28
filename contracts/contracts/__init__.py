"""
MLOps Contracts - Shared schemas and data contracts.

This package contains shared Pydantic models and schemas used across
multiple services in the MLOps platform. Centralizing these contracts
ensures consistency and prevents breaking changes.

Modules:
    schemas.payment_event: UnifiedPaymentEvent and event type mappings
    schemas.inference: Fraud/Retry request/response models
    schemas.dlq: Dead letter queue and webhook result models
    schemas.iceberg: PyArrow schemas for Iceberg tables
"""

__version__ = "0.1.0"
