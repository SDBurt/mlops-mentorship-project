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
| **MLOps Platform** | Feast feature store, MLflow model registry, data quality validation | Complete |
| **Batch Orchestration** | Dagster assets, DBT transformations, medallion architecture | Complete |
| **Analytics Layer** | Superset BI dashboards, DBT marts, Iceberg storage | Complete |

---

## Architecture

```
                                 PAYMENT PIPELINE
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│   Stripe       ┌──────────┐    Kafka    ┌─────────────┐    Kafka    ┌─────────┐  │
│   Webhooks ───>│ Gateway  │───────────> │ Transformer │───────────> │Temporal │  │
│                │ (FastAPI)│             │   (Python)  │             │ Worker  │  │
│                └──────────┘             └─────────────┘             └─────────┘  │
│                     │                        │                          │       │
│                     v                        v                          v       │
│                 [DLQ Topic]             [DLQ Topic]               PostgreSQL    │
│                                                                         │       │
│   Inference Service (ML) <────────────── Feast Online Store <───────────┘       │
│   - Fraud Scoring (Live)                   (Redis Features)             │       │
│   - Churn Prediction (Live)                                             v       │
│   - MLflow Model Registry <───────────────────────────────────────┐     │       │
│                                                                   │     │       │
│                               ┌─────────────────────────────────────────────┐   │
│                               │            LAKEHOUSE PLATFORM               │   │
│                               │  Dagster ──> Iceberg ──> DBT ──> Trino      │   │
│                               │  (ML Ops)   (Bronze)   (Silver)  (query)    │   │
│                               └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Technical Stack

### Payment Pipeline
- **Gateway**: FastAPI, HMAC-SHA256 signature verification, aiokafka
- **Transformer**: ISO 4217 currency validation, null normalization, unified event schema
- **Temporal Worker**: Temporal workflows, per-activity retry policies, idempotent processing
- **Inference**: FastAPI service using **Feast** for real-time features and **MLflow** for model serving

### MLOps Platform
- **Feature Store**: **Feast** with Redis (online) and S3/Iceberg (offline)
- **Model Tracking**: **MLflow** for experiment tracking and model registry
- **Data Quality**: Dagster assets for feature validation and drift detection
- **Champion/Challenger**: Automated model promotion based on performance metrics

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
2. **Transformer**: Currency codes (ISO 4217), amount bounds, null handling
3. **Temporal Worker**: Business rules via Temporal activities

### durable Workflow Execution
- Temporal workflows survive service restarts
- Event-based idempotency (`event_id` as workflow ID)
- Per-activity retry policies with exponential backoff
- Dead letter queues at each processing stage

### End-to-End MLOps Loop
- **Real-time Enrichment**: Inference service retrieves millisecond-latency features from Feast
- **Model Governance**: MLflow manages "Production" vs "Staging" model versions
- **Automated Training**: Dagster orchestrates periodic model retraining with Champion/Challenger logic
- **Data Validation**: Pre-training checks ensure feature quality and catch distribution drift

### Provider-Agnostic Design
- Unified event schema normalizes provider-specific formats
- Pluggable transformer/handler architecture
- Extensible for additional payment providers (Square, PayPal, Adyen)

---

## Project Structure

```
.
├── contracts/                  # Shared schemas package
│   └── schemas/                # Pydantic models for events
│
├── services/                   # Microservices
│   ├── gateway/                # Webhook ingestion (FastAPI)
│   ├── transformer/            # Validation & transformation
│   ├── temporal/               # Temporal workflow worker
│   ├── inference/              # Live ML inference (Feast + MLflow)
│   ├── dagster/                # Pipeline orchestration
│   └── feast/                  # Feature store server
│
├── tools/
│   └── simulator/              # Webhook traffic generator
│
├── dbt/                        # SQL transformations
│
├── infrastructure/
│   ├── kubernetes/             # Helm values, K8s manifests
│   │   ├── dagster/
│   │   ├── trino/
│   │   ├── polaris/
│   │   └── minio/
│   └── docker/                 # Docker Compose for local dev
│
└── docs/                       # Architecture & guides
```

---

## Quick Start

```bash
# Prerequisites: kubectl, helm, docker

# Deploy lakehouse platform
make check && make setup && make deploy

# Start payment pipeline & MLOps stack (Docker Compose)
make all-up

# Initialize feature store
make feast-apply

# Send test webhooks
make gateway-simulator

# Access services
# Dagster:  http://localhost:3000 (Training & ETL)
# MLflow:   http://localhost:5001 (Model Registry)
# Trino:    http://localhost:8080 (SQL Query)
# MinIO:    http://localhost:9001 (Storage Console)
# Superset: http://localhost:8089 (Dashboards)
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
| **MLOps** | Feast, MLflow, scikit-learn |
| **Streaming** | Apache Kafka, aiokafka |
| **Orchestration** | Temporal, Dagster |
| **Data Lake** | Apache Iceberg, Apache Polaris, Trino |
| **Transformations** | DBT, medallion architecture |
| **APIs** | FastAPI, Pydantic v2 |
| **Infrastructure** | Kubernetes, Helm, Docker |
| **Analytics** | Apache Superset |
| **Testing** | pytest, unit & integration tests |

---

## License

Personal portfolio project for demonstration purposes.
