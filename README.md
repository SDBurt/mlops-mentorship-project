# Data Platform & Payment Pipeline

> **Status: Active Development** - This project demonstrates production-grade data engineering patterns. Core infrastructure and payment pipeline are complete; analytics layer is in progress.

A modern data platform built on Kubernetes featuring real-time payment event processing, streaming validation, workflow orchestration, and a lakehouse architecture.

---

## Highlights

| Component | Description | Status |
|-----------|-------------|--------|
| **Payment Pipeline** | Webhook ingestion, multi-layer validation, Temporal workflows | Complete |
| **Streaming Infrastructure** | Kafka, async Python consumers, dead letter queues | Complete |
| **Lakehouse Platform** | Apache Iceberg, Polaris catalog, Trino query engine | Complete |
| **Batch Orchestration** | Dagster assets, DBT transformations, medallion architecture | Complete |
| **Analytics Layer** | Dagster batch ingestion from PostgreSQL to Iceberg | In Progress |

---

## Architecture

```
                                 PAYMENT PIPELINE
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│   Stripe       ┌──────────┐    Kafka    ┌────────────┐    Kafka    ┌─────────┐ │
│   Webhooks ───>│ Gateway  │───────────> │ Normalizer │───────────> │Temporal │ │
│                │ (FastAPI)│             │  (Python)  │             │Workflows│ │
│                └──────────┘             └────────────┘             └─────────┘ │
│                     │                        │                          │      │
│                     v                        v                          v      │
│                 [DLQ Topic]             [DLQ Topic]               PostgreSQL   │
│                                                                         │      │
│   Inference Service (ML)                                                │      │
│   - Fraud Scoring                                                       v      │
│   - Retry Strategy            ┌─────────────────────────────────────────────┐  │
│   - Churn Prediction          │            LAKEHOUSE PLATFORM               │  │
│                               │  Dagster ──> Iceberg ──> DBT ──> Trino      │  │
│                               │  (batch)    (Bronze)   (Silver)  (query)    │  │
│                               └─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Technical Stack

### Payment Pipeline
- **Gateway**: FastAPI, HMAC-SHA256 signature verification, aiokafka
- **Normalizer**: ISO 4217 currency validation, null normalization, unified event schema
- **Orchestrator**: Temporal workflows, per-activity retry policies, idempotent processing
- **Inference**: Mock ML service (fraud, retry optimization, churn prediction)

### Data Platform
- **Storage**: MinIO (S3-compatible), Apache Iceberg tables
- **Catalog**: Apache Polaris REST catalog
- **Query**: Trino distributed SQL
- **Orchestration**: Dagster asset-based pipelines
- **Transformations**: DBT (medallion architecture)
- **Streaming**: Apache Kafka

### Infrastructure
- **Container Orchestration**: Kubernetes
- **Package Management**: Helm
- **Local Development**: Docker Compose

---

## Key Features

### Multi-Layer Validation Pipeline
Three validation layers ensure data quality before lakehouse ingestion:
1. **Gateway**: Signature verification, JSON structure validation
2. **Normalizer**: Currency codes (ISO 4217), amount bounds, null handling
3. **Orchestrator**: Business rules via Temporal activities

### Durable Workflow Execution
- Temporal workflows survive service restarts
- Event-based idempotency (`event_id` as workflow ID)
- Per-activity retry policies with exponential backoff
- Dead letter queues at each processing stage

### Provider-Agnostic Design
- Unified event schema normalizes provider-specific formats
- Pluggable transformer/handler architecture
- Extensible for additional payment providers (Square, PayPal, Adyen)

---

## Project Structure

```
.
├── payment-pipeline/           # Streaming payment processing
│   ├── src/
│   │   ├── payment_gateway/    # Webhook ingestion (FastAPI)
│   │   ├── normalizer/         # Validation & transformation
│   │   └── orchestrator/       # Temporal workflows
│   ├── inference_service/      # Mock ML endpoints
│   └── tests/                  # Unit & integration tests
│
├── infrastructure/
│   ├── kubernetes/             # Helm values, K8s manifests
│   │   ├── dagster/
│   │   ├── trino/
│   │   ├── polaris/
│   │   └── minio/
│   └── docker/                 # Docker Compose for local dev
│
├── orchestration-dagster/      # Batch pipeline orchestration
├── orchestration-dbt/          # SQL transformations
└── docs/                       # Architecture & guides
```

---

## Quick Start

```bash
# Prerequisites: kubectl, helm, docker

# Deploy lakehouse platform
make check && make setup && make deploy

# Start payment pipeline (Docker Compose)
make pipeline-up

# Send test webhooks
make gateway-simulator

# Access services
make port-forward-start
# Dagster:  http://localhost:3001
# Trino:    http://localhost:8080
# MinIO:    http://localhost:9001
```

---

## Documentation

- [Payment Pipeline Design](docs/guides/payment-pipeline.md) - Full system design document
- [Getting Started](docs/guides/getting-started.md) - Setup walkthrough
- [Streaming Setup](docs/guides/streaming-setup.md) - Kafka + Flink configuration

---

## Skills Demonstrated

| Category | Technologies |
|----------|-------------|
| **Languages** | Python 3.11+, SQL |
| **Streaming** | Apache Kafka, aiokafka |
| **Orchestration** | Temporal, Dagster |
| **Data Lake** | Apache Iceberg, Apache Polaris, Trino |
| **Transformations** | DBT, medallion architecture |
| **APIs** | FastAPI, Pydantic v2 |
| **Infrastructure** | Kubernetes, Helm, Docker |
| **Testing** | pytest, unit & integration tests |

---

## License

Personal portfolio project for demonstration purposes.
