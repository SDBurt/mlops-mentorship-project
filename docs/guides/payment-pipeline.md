# Payment Pipeline: System Design & Implementation

**Project:** Streaming Payment Data Platform
**Target Role:** Data Engineer at Butter Payments
**Architecture Style:** Monorepo with Microservice Structure

---

## Executive Summary

This document outlines the design and implementation of a webhook-driven payment processing pipeline demonstrating upstream validation, real-time streaming, and distributed workflow orchestration. The system ingests simulated payment webhooks, validates and normalizes them through a streaming layer, and orchestrates per-event workflows with live ML integration via **Feast** and **MLflow** before persisting to PostgreSQL. A separate Dagster MLOps layer handles feature engineering, data quality validation, and model retraining.

---

## Implementation Status

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Gateway (Stripe webhook ingestion) | Complete |
| Phase 2 | Normalizer (Python aiokafka validation) | Complete |
| Phase 3 | Orchestrator (Temporal workflows) | Complete |
| Phase 4 | MLOps (Feast Features + MLflow Models) | Complete |
| Phase 5 | Analytics Layer (Dagster + DBT + Superset) | Complete |
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
| MLOps | **Inference** | FastAPI + Feast + MLflow | Real-time enrichment and serving for fraud, churn, and recovery |
| MLOps | **Feature Store** | Feast + Redis | Millisecond-latency feature retrieval for online models |
| MLOps | **Retraining** | Dagster + MLflow | Automated training pipelines with data quality checks |
| Analytics | **BI** | DBT + Trino + Superset | Star schema modeling and executive dashboards |

---

## Project Structure

```
.
├── payment-pipeline/           # Streaming payment processing
│   ├── src/
│   │   ├── payment_gateway/    # System 1: Gateway (FastAPI)
│   │   ├── normalizer/         # System 2: Normalizer (aiokafka)
│   │   └── orchestrator/       # System 3: Orchestrator (Temporal)
│   ├── inference_service/      # Live ML inference (Feast + MLflow)
│   └── tests/                  # Unit & integration tests
│
├── mlops/                      # MLOps Infrastructure
│   ├── feature-store/          # Feast repository and server
│   ├── training/               # Model training scripts
│   └── serving/                # Model serving configuration
│
├── orchestration-dagster/      # Pipeline orchestration & ML training
├── orchestration-dbt/          # SQL transformations (Medallion)
├── infrastructure/
│   ├── kubernetes/             # Helm values, K8s manifests
│   └── docker/                 # Docker Compose for local dev
└── docs/                       # Architecture & guides
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

The Inference service is a production-grade ML serving layer that integrates with **Feast** for real-time feature retrieval and **MLflow** for model lifecycle management.

**Endpoints:**

| Endpoint | Purpose | Key Features |
|----------|---------|--------------|
| `POST /fraud/score` | Fraud probability scoring | Real-time Feast features, MLflow Production model |
| `POST /retry/strategy` | Retry timing recommendations | Failure code analysis, historical recovery rates |
| `POST /churn/predict` | Customer churn prediction | Behavioral features from Feast, dynamic risk factors |
| `POST /recovery/recommend` | Failed payment recovery | Multi-step plans based on customer lifetime value |

**ML Integration:**

- **Feast**: Fetches latest customer and merchant metrics (e.g., `total_payments_30d`, `fraud_score_avg`) with millisecond latency from the Redis online store.
- **MLflow**: Automatically loads the latest model versions tagged as "Production" for each endpoint, ensuring seamless deployments.
- **Fallback**: Includes robust fallback logic to mock predictors if MLOps infrastructure is unavailable.

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

### Phase 4: MLOps Integration (Complete)

**Implemented:**
- **Feast** online store (Redis) for real-time feature retrieval
- **MLflow** Model Registry for governing "Production" model versions
- Automated feature export from Lakehouse to Feast
- FastAPI integration with Feast SDK and MLflow client
- Sub-100ms inference latency with live feature enrichment

---

### Phase 5: Analytics & Governance (Complete)

**Implemented:**
- **Dagster** orchestration for batch ingestion (Postgres -> Iceberg)
- **DBT** Medallion architecture (Bronze -> Silver -> Gold)
- **Data Quality** validation assets for ML feature monitoring
- **Superset** dashboards for payment performance and model drift
- **Champion/Challenger** logic for automated model promotion

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

1. **Additional Payment Providers**: Square, PayPal, Adyen (Normalizers & Gateways)
2. **Streaming Features**: Real-time feature aggregation via Kafka Streams or Flink
3. **Schema Registry**: Avro/Protobuf schemas with Confluent Schema Registry
4. **Advanced Monitoring**: Prometheus/Grafana for service health and model observability
5. **Kubernetes Autoscaling**: HPA based on Kafka consumer lag and Inference RPS

---

## Technology Versions

| Technology | Version | Notes |
|------------|---------|-------|
| Python | 3.11+ | All services |
| Apache Kafka | 3.6+ | Via Docker Compose |
| Temporal | 1.22+ | Via Docker Compose |
| Feast | 0.36+ | Feature store with Redis online provider |
| MLflow | 2.19+ | Model registry and experiment tracking |
| Apache Iceberg | 1.5+ | Data lakehouse format |
| Apache Polaris | 0.1+ | Iceberg REST catalog |
| Trino | 440+ | Distributed SQL query engine |
| DBT | 1.7+ | SQL transformations |
| Apache Superset | 3.1+ | BI and data visualization |
| FastAPI | 0.115+ | Gateway, Inference services |
| Pydantic | 2.5+ | All services |
| temporalio | 1.5+ | Orchestrator |
