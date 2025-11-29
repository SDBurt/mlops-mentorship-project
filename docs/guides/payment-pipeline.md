# Payment Pipeline: System Design & Implementation

**Project:** Streaming Payment Data Platform
**Target Role:** Data Engineer at Butter Payments
**Architecture Style:** Monorepo with Microservice Structure

---

## Executive Summary

This document outlines the design and implementation of a webhook-driven payment processing pipeline demonstrating upstream validation, real-time streaming, and distributed workflow orchestration. The system ingests simulated payment webhooks, validates and normalizes them through a streaming layer, and orchestrates per-event workflows with ML integration before persisting to PostgreSQL. A separate Dagster batch layer ingests from PostgreSQL into the Iceberg lakehouse.

---

## Implementation Status

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Gateway (Stripe webhook ingestion) | Complete |
| Phase 2 | Normalizer (Python aiokafka validation) | Complete |
| Phase 3 | Orchestrator (Temporal workflows) | Complete |
| Phase 4 | Inference Service (ML mock endpoints) | Complete |
| Phase 5 | Analytics Layer (Dagster + DBT) | Not Started |
| Phase 6 | Documentation & Polish | In Progress |

---

## System Architecture

### High-Level Data Flow

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              PAYMENT PIPELINE                                    │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Webhooks ──► GATEWAY ──► Kafka ──► NORMALIZER ──► Kafka ──► ORCHESTRATOR        │
│               (FastAPI)    (raw)     (Python)   (normalized)   (Temporal)        │
│                  │                      │                          │             │
│                  ▼                      ▼                          ▼             │
│              [DLQ Topic]          [DLQ Topic]               [PostgreSQL]         │
│                                                                    │             │
│                                                                    ▼             │
│                                                    ┌───────────────────────────┐ │
│                                                    │  ANALYTICS LAYER          │ │
│                                                    │  Dagster (batch ingest)   │ │
│                                                    │  → Iceberg → DBT          │ │
│                                                    │  (Bronze/Silver/Gold)     │ │
│                                                    └───────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### System Components

| System | Name | Technology | Responsibility |
|--------|------|------------|----------------|
| System 1 | **Gateway** | FastAPI + aiokafka | Webhook reception, signature verification, Kafka production |
| System 2 | **Normalizer** | Python + aiokafka | Content validation, schema normalization, DLQ routing |
| System 3 | **Orchestrator** | Temporal + Kafka Consumer | Per-event workflow execution, ML integration, PostgreSQL persistence |
| Support | **Inference** | FastAPI | Mock ML service for fraud, retry, churn, and recovery |
| Support | **Analytics** | Dagster + DBT | Batch transformations, Silver/Gold layer management (future) |

---

## Project Structure (Implemented)

```
payment-pipeline/
│
├── README.md
├── CLAUDE.md                         # Claude Code guidance
├── pyproject.toml                    # Shared dependencies (uv)
├── uv.lock
│
├── src/
│   ├── payment_gateway/              # System 1: Gateway
│   │   ├── main.py                   # FastAPI application
│   │   ├── config.py                 # Pydantic settings
│   │   ├── core/
│   │   │   ├── base_models.py        # Shared Pydantic models
│   │   │   ├── exceptions.py         # Custom exceptions
│   │   │   └── kafka_producer.py     # Async Kafka producer
│   │   └── providers/
│   │       └── stripe/
│   │           ├── models.py         # Stripe webhook Pydantic models
│   │           ├── validator.py      # HMAC-SHA256 signature verification
│   │           └── router.py         # /webhooks/stripe endpoint
│   │
│   ├── normalizer/                   # System 2: Normalizer
│   │   ├── main.py                   # Async Kafka consumer loop
│   │   ├── config.py                 # Pydantic settings (NORMALIZER_ prefix)
│   │   ├── validators/
│   │   │   ├── base.py               # ValidationError, ValidationResult
│   │   │   ├── currency.py           # ISO 4217 validation (20 currencies)
│   │   │   ├── nulls.py              # Null string normalization
│   │   │   └── amount.py             # Amount bounds (0 to $1M)
│   │   ├── transformers/
│   │   │   ├── base.py               # UnifiedPaymentEvent schema
│   │   │   └── stripe.py             # StripeTransformer
│   │   └── handlers/
│   │       └── stripe.py             # StripeHandler, ProcessingResult
│   │
│   └── orchestrator/                 # System 3: Orchestrator
│       ├── main.py                   # Entrypoint (consumer + worker)
│       ├── config.py                 # Pydantic settings (ORCHESTRATOR_ prefix)
│       ├── consumer.py               # Kafka → Temporal bridge
│       ├── models/
│       │   └── inference.py          # Inference request/response models
│       ├── workflows/
│       │   ├── payment_event.py      # PaymentEventWorkflow
│       │   └── dlq_review.py         # DLQReviewWorkflow
│       └── activities/
│           ├── validation.py         # Business rule validation
│           ├── fraud.py              # Call inference /fraud/score
│           ├── retry_strategy.py     # Call inference /retry/strategy
│           ├── churn.py              # Call inference /churn/predict
│           └── postgres.py           # Persist to PostgreSQL
│
├── inference_service/                # Support: Mock ML Service
│   ├── main.py                       # FastAPI application
│   ├── config.py                     # Pydantic settings (INFERENCE_ prefix)
│   └── routes/
│       ├── fraud.py                  # POST /fraud/score
│       ├── retry.py                  # POST /retry/strategy
│       ├── churn.py                  # POST /churn/predict
│       └── recovery.py               # POST /recovery/recommend
│
├── simulator/                        # Webhook generator CLI
│   ├── main.py                       # Click CLI (send, generate commands)
│   └── stripe_generator.py           # Mock Stripe webhook payloads
│
├── tests/
│   ├── unit/
│   │   ├── test_stripe_models.py
│   │   ├── test_stripe_validator.py
│   │   ├── test_normalizer_validators.py
│   │   ├── test_normalizer_transformers.py
│   │   ├── test_normalizer_handlers.py
│   │   ├── test_orchestrator_activities.py
│   │   ├── test_orchestrator_workflows.py
│   │   └── test_inference_service.py
│   └── integration/
│
├── Dockerfile                        # Gateway image
├── Dockerfile.normalizer             # Normalizer image
├── Dockerfile.orchestrator           # Orchestrator image
└── Dockerfile.inference              # Inference service image
```

---

## Component Specifications

### Gateway Service

The Gateway is a FastAPI application that receives webhooks from payment providers, verifies signatures, and publishes to Kafka. Provider-specific logic is isolated in the `providers/` subdirectory.

**Responsibilities:**

1. Receive HTTP POST webhooks from payment providers
2. Validate request structure (valid JSON, required fields)
3. Authenticate webhook signature (provider-specific HMAC verification)
4. Publish raw event to provider-specific Kafka topic
5. Return acknowledgment quickly (minimize latency)
6. Route malformed payloads to dead letter queue

**Kafka Topics Produced:**

| Topic | Purpose | Partition Key |
|-------|---------|---------------|
| `webhooks.stripe.payment_intent` | Payment intent events | `merchant_id` |
| `webhooks.stripe.charge` | Charge events | `merchant_id` |
| `webhooks.stripe.refund` | Refund events | `merchant_id` |
| `webhooks.dlq` | Gateway validation failures | `event_id` |

**Key Design Decisions:**

The gateway performs only structure validation, not semantic validation. This keeps response times low and ensures webhooks are acknowledged before the provider times out. Deeper validation happens in the Normalizer.

---

### Normalizer Service

The Normalizer is a Python async Kafka consumer (aiokafka) that consumes from provider-specific topics, applies content validation, transforms events to a unified schema, and publishes to a normalized topic.

**Why Python over Flink:**
- Aligns with target tech stack (Python, Kafka, Temporal - no Flink in job description)
- Temporal best practices recommend validating upstream, not in workflows
- Simpler deployment and debugging for validation logic
- Industry standard (Stripe, Square use similar patterns)

**Responsibilities:**

1. Consume events from all provider raw topics (async Kafka consumer)
2. Apply content validation rules:
   - Null normalization (convert `'null'`, `'NULL'`, `''`, `'None'` to Python None)
   - Currency code validation (ISO 4217, 20 supported currencies)
   - Amount bounds checking (0 to $1M)
   - Required field validation (event_id, event_type, data.object)
3. Transform provider-specific schemas to `UnifiedPaymentEvent`
4. Add metadata (processing timestamp, schema version, source provider)
5. Publish valid events to `payments.normalized`
6. Route validation failures to DLQ with structured error details

**Kafka Topics:**

| Direction | Topic | Purpose |
|-----------|-------|---------|
| Consume | `webhooks.stripe.payment_intent` | Raw payment intent events |
| Consume | `webhooks.stripe.charge` | Raw charge events |
| Consume | `webhooks.stripe.refund` | Raw refund events |
| Produce | `payments.normalized` | Unified schema events |
| Produce | `payments.validation.dlq` | Validation failures |

**Unified Event Schema:**

```json
{
  "event_id": "stripe:evt_1abc123",
  "provider": "stripe",
  "provider_event_id": "evt_1abc123",
  "event_type": "payment.succeeded",
  "merchant_id": "merch_456",
  "customer_id": "cus_789",
  "amount_cents": 5000,
  "currency": "USD",
  "payment_method_type": "card",
  "card_brand": "visa",
  "card_last_four": "4242",
  "status": "succeeded",
  "failure_code": null,
  "failure_message": null,
  "metadata": {},
  "provider_created_at": "2025-01-15T10:30:00Z",
  "processed_at": "2025-01-15T10:30:01Z",
  "schema_version": 1
}
```

---

### Orchestrator Service (Temporal)

The Orchestrator consists of two components: a Kafka consumer that bridges events to Temporal, and Temporal workers that execute payment event workflows.

**Consumer Component:**

The consumer reads from `payments.normalized` and `payments.validation.dlq`, and starts a Temporal workflow for each event. It uses `event_id` as workflow ID with `WorkflowIDConflictPolicy.USE_EXISTING` for idempotency.

**Workflow Definitions:**

```
PaymentEventWorkflow(event)
│
├── 1. validate_business_rules(event)
│      └── Final validation that requires business context
│
├── 2. get_fraud_score(event)  [if successful payment]
│      └── Call Inference service for fraud probability
│
├── 3. get_retry_strategy(event)  [if failed payment]
│      └── Call Inference service for optimal retry timing
│
├── 4. get_churn_prediction(event)
│      └── Call Inference service for churn risk assessment
│
└── 5. persist_to_postgres(event, scores)
       └── Write enriched event to PostgreSQL (Dagster batch ingests to Iceberg)


DLQReviewWorkflow(event)
│
└── Persist quarantined event to PostgreSQL quarantine table
```

**Activities:**

| Activity | Description | Retry Policy |
|----------|-------------|--------------|
| `validate_business_rules` | Blocklist check, amount limits | 3 retries, 1s backoff |
| `get_fraud_score` | Call inference `/fraud/score` | 5 retries, exponential backoff |
| `get_retry_strategy` | Call inference `/retry/strategy` | 5 retries, exponential backoff |
| `get_churn_prediction` | Call inference `/churn/predict` | 5 retries, exponential backoff |
| `persist_to_postgres` | Write to PostgreSQL via psycopg3 | 5 retries, exponential backoff |

**Key Design Decisions:**

Temporal provides durable execution - workflows survive service restarts. The workflow ID uses `event_id` to ensure idempotency. If the same event is processed twice, Temporal returns the existing workflow result rather than creating a duplicate.

---

### Inference Service

The Inference service is a mock ML service that simulates predictions. It returns deterministic results based on input features for reproducibility.

**Endpoints:**

| Endpoint | Purpose | Key Features |
|----------|---------|--------------|
| `POST /fraud/score` | Fraud probability scoring | Amount thresholds, guest checkout, card brand risk |
| `POST /retry/strategy` | Retry timing recommendations | Failure code analysis, exponential backoff |
| `POST /churn/predict` | Customer churn prediction | Payment history, consecutive failures |
| `POST /recovery/recommend` | Failed payment recovery | Multi-step plans, backup payment methods |

**Mock Logic:**

Fraud score is computed based on amount, customer history flags, and card type. Retry strategy considers failure codes and previous attempt count. Churn prediction analyzes payment patterns. Recovery recommends optimal actions based on failure type and customer value.

---

## Development Phases

### Phase 1: Gateway (Complete)

**Implemented:**
- FastAPI application with `/webhooks/stripe` endpoint
- HMAC-SHA256 signature verification
- Pydantic v2 models with discriminated unions
- Per-event-type Kafka topics
- Dead letter queue for invalid payloads
- Webhook simulator CLI

---

### Phase 2: Normalizer (Complete)

**Implemented:**
- Python async Kafka consumer (aiokafka)
- Null normalization (`'null'`, `'NULL'`, `''`, `'None'` → None)
- ISO 4217 currency validation (20 currencies)
- Amount bounds checking (0 to $1M)
- UnifiedPaymentEvent transformation
- Structured DLQ payloads with error details

**Note:** Originally planned for Flink, implemented with Python aiokafka for simpler deployment and better alignment with target tech stack.

---

### Phase 3: Orchestrator (Complete)

**Implemented:**
- Temporal workflows triggered by Kafka events
- `PaymentEventWorkflow` with 5-step activity sequence
- `DLQReviewWorkflow` for quarantined events
- Idempotency via event_id as workflow ID
- PostgreSQL persistence (Dagster batch layer ingests to Iceberg)
- Churn prediction integration
- Per-activity retry policies

---

### Phase 4: Inference Service (Complete)

**Implemented:**
- FastAPI application with 4 ML endpoints
- Fraud scoring based on event features
- Retry strategy recommendations
- Churn prediction (added based on Butter Payments focus)
- Payment recovery planning (added for involuntary churn reduction)
- Deterministic mock logic for testing

---

### Phase 5: Analytics Layer (Not Started)

**Planned:**
- Dagster integration with Iceberg resources
- DBT models for Silver/Gold transformations
- Data quality tests
- Quarantine rate monitoring

**Note:** Analytics layer exists in parent repository (`orchestration-dagster/`, `transformations/dbt/`).

---

### Phase 6: Documentation & Polish (In Progress)

**Completed:**
- README with architecture overview
- CLAUDE.md for Claude Code guidance
- Unit tests for all services

**Remaining:**
- End-to-end demo script
- Monitoring dashboards
- Video recording

---

## Kafka Topic Design

### Topic Inventory (Implemented)

| Topic | Purpose | Producer | Consumer |
|-------|---------|----------|----------|
| `webhooks.stripe.payment_intent` | Raw payment intent events | Gateway | Normalizer |
| `webhooks.stripe.charge` | Raw charge events | Gateway | Normalizer |
| `webhooks.stripe.refund` | Raw refund events | Gateway | Normalizer |
| `webhooks.dlq` | Gateway validation failures | Gateway | - |
| `payments.normalized` | Unified schema events | Normalizer | Orchestrator |
| `payments.validation.dlq` | Normalizer validation failures | Normalizer | Orchestrator |

---

## Testing Strategy

### Unit Tests (Implemented)

| Test File | Coverage |
|-----------|----------|
| `test_stripe_models.py` | Gateway Pydantic models |
| `test_stripe_validator.py` | Signature verification |
| `test_normalizer_validators.py` | Currency, amount, null validation |
| `test_normalizer_transformers.py` | Schema transformation |
| `test_normalizer_handlers.py` | Event processing |
| `test_orchestrator_activities.py` | Temporal activities |
| `test_orchestrator_workflows.py` | Workflow definitions |
| `test_inference_service.py` | All 4 ML endpoints |

### Running Tests

```bash
cd payment-pipeline
uv sync --extra dev
uv run pytest tests/unit/ -v
```

---

## Future Enhancements

1. **Additional Payment Providers**: Square, PayPal, Adyen
2. **Real ML Models**: Replace mock inference with trained models
3. **Schema Registry**: Avro schemas with Confluent Schema Registry
4. **Monitoring**: Prometheus metrics, Grafana dashboards
5. **Kubernetes Deployment**: Helm charts for production deployment

---

## Technology Versions

| Technology | Version | Notes |
|------------|---------|-------|
| Python | 3.11+ | All services |
| Apache Kafka | 3.6+ | Via Docker Compose |
| Temporal | 1.22+ | Via Docker Compose |
| PostgreSQL | 15+ | Orchestrator persistence (Dagster ingests to Iceberg) |
| FastAPI | 0.109+ | Gateway, Inference |
| aiokafka | 0.10+ | Gateway, Normalizer, Orchestrator |
| psycopg | 3.1+ | Orchestrator PostgreSQL driver |
| Pydantic | 2.5+ | All services |
| temporalio | 1.5+ | Orchestrator |
