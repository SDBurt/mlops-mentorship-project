# Payment Pipeline: System Design & Development Outline

**Project:** Streaming Payment Data Platform
**Target Role:** Data Engineer at Butter Payments
**Architecture Style:** Monorepo with Microservice Structure

---

## Executive Summary

This document outlines the design and implementation plan for a webhook-driven payment processing pipeline that demonstrates upstream validation, real-time streaming, and distributed workflow orchestration. The system ingests simulated payment webhooks from multiple providers, validates and normalizes them through a streaming layer, and orchestrates per-event workflows with ML integration before landing data in an Iceberg-based lakehouse.

The architecture consists of three primary systems, each with a focused responsibility, plus supporting infrastructure for data transformation and analytics.

---

## System Architecture

### High-Level Data Flow

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              PAYMENT PIPELINE                                    │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Webhooks ──► GATEWAY ──► Kafka ──► NORMALIZER ──► Kafka ──► ORCHESTRATOR        │
│               (Ingest)     (raw)     (Flink)    (normalized)   (Temporal)        │
│                  │                      │                          │             │
│                  ▼                      ▼                          ▼             │
│              [DLQ Topic]          [Quarantine]              [Iceberg Bronze]     │
│                                                                    │             │
│                                                                    ▼             │
│                                                    ┌───────────────────────────┐ │
│                                                    │  ANALYTICS LAYER          │ │
│                                                    │  Dagster → DBT → Iceberg  │ │
│                                                    │  (Silver/Gold Layers)     │ │
│                                                    └───────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### System Components

| System | Name | Technology | Responsibility |
|--------|------|------------|----------------|
| System 1 | **Gateway** | FastAPI | Webhook reception, structure validation, Kafka production |
| System 2 | **Normalizer** | Apache Flink | Extended validation, schema normalization, stream processing |
| System 3 | **Orchestrator** | Temporal + Kafka Consumer | Per-event workflow execution, ML integration, lake persistence |
| Support | **Inference** | FastAPI | Mock ML service for retry strategy and fraud scoring |
| Support | **Analytics** | Dagster + DBT | Batch transformations, Silver/Gold layer management |

---

## Project Structure

The repository follows a monorepo pattern with microservice-organized folders. Each service is independently deployable but shares common schemas and utilities.

```
payment-pipeline/
│
├── README.md
├── docker-compose.yml                    # Local development environment
├── Makefile                              # Common commands (build, test, deploy)
│
├── services/
│   │
│   ├── gateway-stripe/                   # Stripe webhook ingestion
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                   # FastAPI application
│   │   │   ├── routes/
│   │   │   │   └── webhooks.py           # Webhook endpoint handlers
│   │   │   ├── validators/
│   │   │   │   └── structure.py          # JSON structure validation
│   │   │   ├── producers/
│   │   │   │   └── kafka.py              # Kafka producer client
│   │   │   └── config.py
│   │   └── tests/
│   │       └── test_webhooks.py
│   │
│   ├── gateway-square/                   # Square webhook ingestion
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── routes/
│   │   │   │   └── webhooks.py
│   │   │   ├── validators/
│   │   │   │   └── structure.py
│   │   │   ├── producers/
│   │   │   │   └── kafka.py
│   │   │   └── config.py
│   │   └── tests/
│   │       └── test_webhooks.py
│   │
│   ├── normalizer/                       # Flink stream processing
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── jobs/
│   │   │   │   ├── stripe_normalizer.py  # Stripe → unified schema
│   │   │   │   └── square_normalizer.py  # Square → unified schema
│   │   │   ├── validators/
│   │   │   │   ├── currency.py           # ISO 4217 validation
│   │   │   │   ├── nulls.py              # Null normalization
│   │   │   │   └── amounts.py            # Amount bounds checking
│   │   │   ├── transformers/
│   │   │   │   ├── stripe.py             # Stripe schema mapping
│   │   │   │   └── square.py             # Square schema mapping
│   │   │   └── config.py
│   │   ├── sql/                          # Flink SQL definitions (alternative)
│   │   │   ├── stripe_source.sql
│   │   │   ├── square_source.sql
│   │   │   └── normalized_sink.sql
│   │   └── tests/
│   │       ├── test_validators.py
│   │       └── test_transformers.py
│   │
│   ├── orchestrator/                     # Temporal workflows
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── consumer.py               # Kafka → Temporal bridge
│   │   │   ├── worker.py                 # Temporal worker entrypoint
│   │   │   ├── workflows/
│   │   │   │   └── payment_event.py      # PaymentEventWorkflow definition
│   │   │   ├── activities/
│   │   │   │   ├── validation.py         # Final business rule validation
│   │   │   │   ├── ml_inference.py       # Call ML service for scoring
│   │   │   │   ├── iceberg_writer.py     # Persist to Bronze layer
│   │   │   │   └── database_writer.py    # Persist to operational DB
│   │   │   └── config.py
│   │   └── tests/
│   │       ├── test_workflows.py
│   │       └── test_activities.py
│   │
│   └── inference/                        # Mock ML service
│       ├── Dockerfile
│       ├── pyproject.toml
│       ├── src/
│       │   ├── __init__.py
│       │   ├── main.py                   # FastAPI application
│       │   ├── routes/
│       │   │   ├── retry_strategy.py     # Retry timing recommendations
│       │   │   └── fraud_score.py        # Fraud probability scoring
│       │   ├── models/
│       │   │   └── mock_models.py        # Simulated ML logic
│       │   └── config.py
│       └── tests/
│           └── test_inference.py
│
├── shared/                               # Shared libraries across services
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── unified.py                    # Unified payment event schema
│   │   ├── stripe.py                     # Stripe webhook schema
│   │   ├── square.py                     # Square webhook schema
│   │   └── avro/                         # Avro schemas for Kafka
│   │       ├── payment_event.avsc
│   │       └── provider_event.avsc
│   │
│   └── utils/
│       ├── __init__.py
│       ├── kafka.py                      # Shared Kafka utilities
│       ├── logging.py                    # Structured logging setup
│       └── metrics.py                    # Prometheus metrics helpers
│
├── infrastructure/
│   │
│   ├── k8s/
│   │   ├── namespace.yaml
│   │   ├── gateway/
│   │   │   ├── stripe-deployment.yaml
│   │   │   ├── stripe-service.yaml
│   │   │   ├── square-deployment.yaml
│   │   │   └── square-service.yaml
│   │   ├── normalizer/
│   │   │   └── flink-deployment.yaml
│   │   ├── orchestrator/
│   │   │   ├── consumer-deployment.yaml
│   │   │   └── worker-deployment.yaml
│   │   ├── inference/
│   │   │   ├── deployment.yaml
│   │   │   └── service.yaml
│   │   ├── kafka/
│   │   │   └── strimzi-cluster.yaml
│   │   └── temporal/
│   │       └── temporal-helm-values.yaml
│   │
│   └── helm/
│       └── payment-pipeline/
│           ├── Chart.yaml
│           ├── values.yaml
│           └── templates/
│
├── generators/                           # Test data generation
│   ├── stripe_webhooks.py                # Generate mock Stripe webhooks
│   ├── square_webhooks.py                # Generate mock Square webhooks
│   └── templates/
│       ├── stripe_payment_intent.json
│       └── square_payment.json
│
├── analytics/
│   │
│   ├── dagster/
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── definitions.py            # Dagster definitions
│   │   │   ├── assets/
│   │   │   │   ├── bronze.py             # Bronze layer assets
│   │   │   │   ├── silver.py             # Silver layer assets
│   │   │   │   └── gold.py               # Gold layer assets
│   │   │   ├── resources/
│   │   │   │   ├── iceberg.py            # Iceberg catalog resource
│   │   │   │   └── dbt.py                # DBT resource
│   │   │   └── schedules.py              # Hourly/daily schedules
│   │   └── dagster.yaml
│   │
│   └── dbt/
│       ├── dbt_project.yml
│       ├── profiles.yml
│       ├── models/
│       │   ├── staging/
│       │   │   └── stg_payments.sql
│       │   ├── silver/
│       │   │   ├── payments_cleaned.sql
│       │   │   └── schema.yml
│       │   └── gold/
│       │       ├── daily_metrics.sql
│       │       ├── merchant_summary.sql
│       │       └── schema.yml
│       ├── macros/
│       │   └── null_handling.sql
│       └── tests/
│           └── generic/
│
└── docs/
    ├── architecture.md
    ├── development.md
    ├── deployment.md
    └── diagrams/
        ├── data-flow.png
        └── system-architecture.png
```

---

## Component Specifications

### Gateway Services

The Gateway services are lightweight FastAPI applications responsible for receiving webhooks from payment providers. Each provider has its own gateway instance to isolate provider-specific logic and enable independent scaling.

**Responsibilities:**

1. Receive HTTP POST webhooks from payment providers
2. Validate the request structure (is it valid JSON? are required fields present?)
3. Authenticate the webhook signature (provider-specific verification)
4. Publish the raw event to a provider-specific Kafka topic
5. Return acknowledgment to the provider quickly (minimize latency)
6. Route malformed payloads to a dead letter queue

**Kafka Topics Produced:**

| Gateway | Topic | Partition Key |
|---------|-------|---------------|
| gateway-stripe | `payments.stripe.raw` | `merchant_id` |
| gateway-square | `payments.square.raw` | `merchant_id` |
| Both | `payments.ingestion.dlq` | `event_id` |

**Key Design Decisions:**

The gateway performs only structure validation, not semantic validation. This keeps response times low and ensures webhooks are acknowledged before the provider times out. Deeper validation happens in the Normalizer. Each provider gateway is a separate service rather than a single gateway with provider routing because provider webhook formats, authentication mechanisms, and rate limits differ significantly. Separate services allow independent deployment and scaling.

---

### Normalizer Service (Flink)

The Normalizer is an Apache Flink application that consumes from provider-specific topics, applies extended validation, transforms events to a unified schema, and publishes to a normalized topic.

**Responsibilities:**

1. Consume events from all provider raw topics
2. Apply extended validation rules:
   - Null normalization (convert `'null'`, `'NULL'`, `''` to actual null)
   - Currency code validation (ISO 4217 three-letter codes)
   - Amount bounds checking (positive, within reasonable limits)
   - Timestamp parsing and standardization (ISO 8601 UTC)
3. Transform provider-specific schemas to a unified schema
4. Add metadata (processing timestamp, schema version, source provider)
5. Publish valid events to `payments.normalized`
6. Route validation failures to quarantine topic with failure reason

**Kafka Topics:**

| Direction | Topic | Purpose |
|-----------|-------|---------|
| Consume | `payments.stripe.raw` | Raw Stripe events |
| Consume | `payments.square.raw` | Raw Square events |
| Produce | `payments.normalized` | Unified schema events |
| Produce | `payments.validation.dlq` | Validation failures |

**Unified Event Schema:**

```json
{
  "event_id": "uuid-v4",
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

**Key Design Decisions:**

Flink provides exactly-once semantics when configured with checkpointing and Kafka transactions. This ensures no duplicate events in the normalized topic even during failures. The unified schema is designed to be provider-agnostic while retaining enough detail for analytics and ML. Provider-specific fields that don't map to the unified schema are preserved in the `metadata` JSON field.

---

### Orchestrator Service (Temporal)

The Orchestrator consists of two components: a Kafka consumer that bridges events to Temporal, and Temporal workers that execute payment event workflows.

**Consumer Component:**

The consumer reads from `payments.normalized`, handles schema versioning, and starts a Temporal workflow for each event. It maintains exactly-once semantics by committing Kafka offsets only after successful workflow start.

**Workflow Component:**

Each event triggers a `PaymentEventWorkflow` that executes a series of activities. The workflow is idempotent (safe to retry) and uses the `event_id` as the workflow ID to prevent duplicates.

**Workflow Definition:**

```
PaymentEventWorkflow(event)
│
├── 1. validate_business_rules(event)
│      └── Final validation that requires business context
│
├── 2. get_fraud_score(event)
│      └── Call Inference service for fraud probability
│
├── 3. get_retry_strategy(event)  [if applicable]
│      └── Call Inference service for optimal retry timing
│
├── 4. persist_to_iceberg(event, scores)
│      └── Write enriched event to Bronze layer
│
└── 5. persist_to_database(event, scores)  [optional]
       └── Write to operational PostgreSQL for real-time queries
```

**Activities:**

| Activity | Description | Retry Policy |
|----------|-------------|--------------|
| `validate_business_rules` | Cross-reference validation, merchant status checks | 3 retries, 1s backoff |
| `get_fraud_score` | Call ML inference endpoint | 5 retries, exponential backoff |
| `get_retry_strategy` | Call ML inference endpoint | 5 retries, exponential backoff |
| `persist_to_iceberg` | Write to Iceberg via PyIceberg | 10 retries, exponential backoff |
| `persist_to_database` | Write to PostgreSQL | 5 retries, exponential backoff |

**Key Design Decisions:**

Temporal provides durable execution, meaning workflows survive service restarts. If the Orchestrator pod crashes mid-workflow, Temporal resumes from the last completed activity. This is critical for payment processing where data loss is unacceptable. The workflow ID uses the `event_id` to ensure idempotency. If the same event is somehow processed twice, Temporal returns the existing workflow result rather than creating a duplicate.

---

### Inference Service

The Inference service is a mock ML service that simulates the kind of predictions Butter's ML team would provide. It returns deterministic results based on input features for reproducibility.

**Endpoints:**

| Endpoint | Input | Output |
|----------|-------|--------|
| `POST /fraud/score` | Payment event | `{ "score": 0.0-1.0, "risk_level": "low/medium/high" }` |
| `POST /retry/strategy` | Failed payment context | `{ "should_retry": bool, "delay_seconds": int, "max_attempts": int }` |

**Mock Logic:**

The fraud score is computed based on amount, customer history flags, and card type. The retry strategy considers failure codes, time of day, and previous attempt count. These are simplified heuristics that demonstrate the integration pattern without requiring actual ML models.

---

### Analytics Layer (Dagster + DBT)

The Analytics layer transforms Bronze data into Silver and Gold layers for reporting and ML feature engineering.

**Dagster Responsibilities:**

1. Schedule DBT runs (hourly for Silver, daily for Gold)
2. Monitor data freshness and quality metrics
3. Trigger alerts on quarantine rate spikes
4. Provide lineage visibility across the pipeline

**DBT Model Layers:**

| Layer | Purpose | Refresh |
|-------|---------|---------|
| Bronze | Raw validated events from Orchestrator | Real-time |
| Silver | Deduplicated, enriched, joined with dimensions | Hourly |
| Gold | Aggregated metrics, ML features | Daily |

**Key Models:**

- `silver.payments_cleaned`: Deduplicated payments with merchant and customer dimensions
- `silver.payments_quarantine`: Consolidated validation failures for analysis
- `gold.daily_payment_metrics`: Daily aggregates by merchant, provider, status
- `gold.merchant_health_scores`: Derived metrics for merchant risk assessment

---

## Development Phases

### Phase 1: Foundation (Week 1-2)

**Objective:** Establish Kafka infrastructure and implement the first Gateway service.

**Features to Build:**

1. **Kafka Cluster Setup**
   - Deploy Strimzi Kafka operator to Kubernetes
   - Create topics: `payments.stripe.raw`, `payments.normalized`, DLQ topics
   - Configure Schema Registry for Avro schemas
   - Set up topic partitioning (6 partitions per topic, keyed by merchant_id)

2. **Gateway Stripe Service**
   - FastAPI application with `/webhooks/stripe` endpoint
   - Structure validation using Pydantic models
   - Kafka producer with idempotent delivery
   - Health check and readiness endpoints
   - Dockerfile and Kubernetes deployment manifests

3. **Webhook Generator**
   - Python script to generate mock Stripe webhook payloads
   - Configurable event types (payment_intent.succeeded, payment_intent.failed)
   - Configurable rate (events per second)
   - HTTP client to POST to Gateway

**Success Criteria:**

- Kafka cluster running with 3 brokers
- Gateway receives webhooks and publishes to Kafka
- Can observe messages in `payments.stripe.raw` using kafka-console-consumer
- Generator produces 10 events/second without errors

---

### Phase 2: Stream Processing (Week 3-4)

**Objective:** Implement the Normalizer with Flink for validation and transformation.

**Features to Build:**

1. **Flink Cluster Setup**
   - Deploy Flink Kubernetes Operator
   - Configure checkpointing to MinIO (S3)
   - Set up Flink job manager and task managers

2. **Normalizer Job - Stripe**
   - PyFlink or Flink SQL job consuming `payments.stripe.raw`
   - Null normalization functions
   - Currency validation (ISO 4217 lookup)
   - Amount bounds checking
   - Schema transformation to unified format
   - Production to `payments.normalized`

3. **Validation Quarantine**
   - Route invalid events to `payments.validation.dlq`
   - Include failure reason and original payload
   - Create Iceberg table for quarantine analysis

4. **Second Provider - Square**
   - Gateway Square service (similar structure to Stripe)
   - Normalizer job for Square events
   - Square webhook generator

**Success Criteria:**

- Flink job processes Stripe events end-to-end
- Invalid events (bad currency, null amounts) route to quarantine
- Normalized events appear in `payments.normalized` with unified schema
- Square pipeline works independently

---

### Phase 3: Workflow Orchestration (Week 5-6)

**Objective:** Implement Temporal workflows triggered by normalized events.

**Features to Build:**

1. **Temporal Cluster Setup**
   - Deploy Temporal using Helm chart
   - Configure PostgreSQL for Temporal persistence
   - Set up Temporal Web UI access

2. **Kafka-Temporal Consumer**
   - Python service consuming `payments.normalized`
   - Workflow triggering with event_id as workflow ID
   - Offset management for exactly-once semantics
   - Schema version routing

3. **PaymentEventWorkflow**
   - Workflow definition with activity sequence
   - Activity implementations (initially stubs)
   - Retry policies per activity
   - Workflow timeout configuration

4. **Iceberg Writer Activity**
   - PyIceberg integration for Bronze table writes
   - Batch buffering (write every N events or T seconds)
   - Schema evolution handling

**Success Criteria:**

- Temporal UI shows workflows executing
- Events flow from Kafka through Temporal to Iceberg
- Workflows survive worker restarts (durability test)
- Can query Bronze table via Trino

---

### Phase 4: ML Integration (Week 7-8)

**Objective:** Add the Inference service and integrate with workflows.

**Features to Build:**

1. **Inference Service**
   - FastAPI application with fraud and retry endpoints
   - Mock scoring logic based on event features
   - Response latency simulation (50-200ms)
   - Kubernetes deployment

2. **ML Activity Integration**
   - `get_fraud_score` activity calling Inference service
   - `get_retry_strategy` activity calling Inference service
   - Enrich events with scores before Iceberg write

3. **Activity Retry Logic**
   - Exponential backoff for Inference service failures
   - Circuit breaker pattern for sustained failures
   - Fallback scores when ML is unavailable

**Success Criteria:**

- Workflows call Inference service and enrich events
- Iceberg Bronze contains fraud_score and retry_strategy fields
- ML service failures trigger retries, not workflow failures
- Fallback behavior works when Inference is down

---

### Phase 5: Analytics Layer (Week 9)

**Objective:** Implement Silver/Gold transformations with Dagster and DBT.

**Features to Build:**

1. **Dagster Integration**
   - Dagster project with Iceberg resources
   - DBT integration via dagster-dbt
   - Schedules for hourly and daily runs

2. **DBT Models**
   - Silver: `payments_cleaned` with deduplication
   - Silver: `payments_quarantine` consolidated view
   - Gold: `daily_payment_metrics` aggregations
   - Gold: `merchant_health_scores` derived metrics

3. **Data Quality Tests**
   - DBT tests for uniqueness, not-null, accepted values
   - dbt-expectations for statistical tests
   - Quarantine rate monitoring

**Success Criteria:**

- Dagster schedules run DBT transformations
- Silver and Gold tables populated with correct data
- Data quality tests pass
- Dagster UI shows lineage and run history

---

### Phase 6: Documentation & Polish (Week 10)

**Objective:** Finalize documentation and create demonstration materials.

**Features to Build:**

1. **README and Documentation**
   - Comprehensive README with architecture diagram
   - Quick start guide (one-command local deployment)
   - API documentation for all services

2. **Monitoring Dashboards**
   - Grafana dashboards for Kafka, Flink, Temporal metrics
   - Quarantine rate alerts
   - End-to-end latency tracking

3. **Demo Script**
   - Scripted demonstration of full pipeline
   - Failure scenario demonstrations (ML down, validation failures)
   - Video recording of demo

**Success Criteria:**

- New developer can run the full stack locally in 15 minutes
- All services have health checks and metrics endpoints
- Demo clearly shows all job requirements being met

---

## Kafka Topic Design

### Topic Inventory

| Topic | Purpose | Partitions | Retention | Key |
|-------|---------|------------|-----------|-----|
| `payments.stripe.raw` | Raw Stripe webhooks | 6 | 7 days | `merchant_id` |
| `payments.square.raw` | Raw Square webhooks | 6 | 7 days | `merchant_id` |
| `payments.normalized` | Unified schema events | 12 | 14 days | `merchant_id` |
| `payments.ingestion.dlq` | Gateway failures | 3 | 30 days | `event_id` |
| `payments.validation.dlq` | Normalizer failures | 3 | 30 days | `event_id` |

### Partitioning Strategy

Events are partitioned by `merchant_id` to ensure all events for a single merchant are processed in order. This is important because payment events for the same merchant may have dependencies (e.g., a refund references a prior charge). With merchant-based partitioning, a single consumer instance handles all events for a given merchant, maintaining ordering guarantees.

### Schema Registry

All topics use Avro schemas registered in Confluent Schema Registry. This enables schema evolution (adding fields, changing types with compatibility rules) without breaking consumers. The `schema_version` field in events allows the Orchestrator to route events to version-appropriate processing logic.

---

## Testing Strategy

### Unit Tests

Each service has unit tests covering core logic. Validators, transformers, and activities are tested in isolation with mock dependencies.

**Coverage Targets:**

- Gateway validators: 90%+
- Normalizer transformers: 95%+
- Orchestrator activities: 85%+
- Inference models: 80%+

### Integration Tests

Integration tests verify service interactions using Testcontainers for Kafka and PostgreSQL.

**Key Integration Tests:**

- Gateway → Kafka: Events published correctly
- Kafka → Normalizer → Kafka: Transformation accuracy
- Kafka → Orchestrator → Iceberg: End-to-end workflow
- Orchestrator → Inference: ML activity integration

### End-to-End Tests

E2E tests run against the full Kubernetes deployment in a test namespace.

**Scenarios:**

1. Happy path: Event flows from webhook to Gold layer
2. Validation failure: Invalid event quarantined correctly
3. ML service down: Workflow retries and eventually succeeds
4. Worker crash: Workflow resumes from checkpoint

---

## Success Metrics

### Technical Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Ingestion latency (Gateway → Kafka) | < 50ms p99 | Prometheus histogram |
| Normalization latency (Kafka → Kafka) | < 200ms p99 | Flink metrics |
| Workflow duration (Kafka → Iceberg) | < 2s p95 | Temporal metrics |
| Validation pass rate | > 99% | Quarantine ratio |
| Workflow success rate | > 99.5% | Temporal dashboard |
| Data freshness (Bronze) | < 30s | Dagster sensors |

### Portfolio Metrics

| Metric | Target |
|--------|--------|
| README completeness | Covers all job requirements |
| One-command startup | Works on fresh machine |
| Demo video length | 5-10 minutes |
| Architecture diagram clarity | Non-technical person understands flow |

---

## Appendix: Technology Versions

| Technology | Version | Notes |
|------------|---------|-------|
| Python | 3.11+ | All services |
| Apache Kafka | 3.6+ | Via Strimzi |
| Apache Flink | 1.18+ | Via Flink Operator |
| Temporal | 1.22+ | Via Helm |
| Apache Iceberg | 1.4+ | Via PyIceberg |
| DBT | 1.7+ | dbt-core with dbt-trino |
| Dagster | 1.6+ | With dagster-dbt |
| Polaris | Latest | Iceberg REST catalog |
| MinIO | Latest | S3-compatible storage |
| Trino | 435+ | Query engine |
