# MLOps Contracts

Shared schemas and data contracts for the MLOps platform.

## Schemas

- `payment_event.py` - UnifiedPaymentEvent and event type mappings
- `inference.py` - Fraud, Retry, and Churn inference models
- `dlq.py` - Dead letter queue and webhook result models
- `iceberg.py` - PyArrow schemas for Iceberg tables

## SQL

- `payment_events.sql` - PostgreSQL DDL for payment tables
