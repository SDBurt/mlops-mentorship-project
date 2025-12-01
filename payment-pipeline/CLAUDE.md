# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

It's 2025. Payment Pipeline is a webhook-driven payment processing system demonstrating upstream validation, real-time streaming, and distributed workflow orchestration. See `docs/guides/payment-pipeline.md` for the full design document.

**Architecture:** Webhooks -> Gateway -> Kafka -> Normalizer -> Kafka -> Temporal Orchestrator -> PostgreSQL (Dagster batch -> Iceberg)

| System | Component | Technology | Status |
|--------|-----------|------------|--------|
| System 1 | Gateway | FastAPI + aiokafka | Complete |
| System 2 | Normalizer | Python aiokafka (not Flink) | Complete |
| System 3 | Orchestrator | Temporal + Kafka Consumer | Complete |
| Support | Inference | FastAPI (mock ML) | Complete |

## Commands

```bash
# Install dependencies
uv sync --extra dev

# Run all unit tests
uv run pytest tests/unit/ -v

# Run specific test file or class
uv run pytest tests/unit/test_inference_service.py -v
uv run pytest tests/unit/test_inference_service.py::TestChurnPrediction -v

# Run tests matching pattern
uv run pytest -k "fraud" -v

# Lint
uv run ruff check .
uv run ruff format .
```

### Running Services Locally

```bash
# Gateway (port 8000)
uvicorn payment_gateway.main:app --reload --port 8000

# Normalizer
python -m normalizer.main

# Inference Service (port 8002)
uvicorn inference_service.main:app --reload --port 8002
```

### Simulator

```bash
uv run simulator send --type payment_intent.succeeded
uv run simulator generate --rate 5 --duration 60
uv run simulator send --type payment_intent.succeeded --invalid-signature
```

### Docker Compose (from repo root)

```bash
make pipeline-up          # Full pipeline (Kafka + Gateway + Normalizer)
make orchestrator-up      # Add Temporal orchestrator
make gateway-simulator    # Start webhook simulator
```

## Architecture

### Data Flow

```
Stripe Webhook --> Gateway --> Kafka (webhooks.stripe.*) --> Normalizer
                                                                  |
                                              +-------------------+-------------------+
                                              |                                       |
                                              v                                       v
                                    payments.normalized                    payments.validation.dlq
                                              |                                       |
                                              v                                       v
                                    PaymentEventWorkflow                    DLQReviewWorkflow
                                              |                                       |
                           +------------------+------------------+                     v
                           |                  |                  |              PostgreSQL
                           v                  v                  v             (quarantine)
                     Validation        Fraud/Retry/       PostgreSQL
                                         Churn               |
                                       Inference             v
                                                      Dagster Batch
                                                             |
                                                             v
                                                      Iceberg Bronze
```

### Service Configuration

All services use Pydantic Settings with environment variable prefixes:

| Service | Prefix | Config File |
|---------|--------|-------------|
| Gateway | (none) | `src/payment_gateway/config.py` |
| Normalizer | `NORMALIZER_` | `src/normalizer/config.py` |
| Orchestrator | `ORCHESTRATOR_` | `src/orchestrator/config.py` |
| Inference | `INFERENCE_` | `inference_service/config.py` |

### Kafka Topics

| Topic | Producer | Consumer |
|-------|----------|----------|
| `webhooks.stripe.payment_intent` | Gateway | Normalizer |
| `webhooks.stripe.charge` | Gateway | Normalizer |
| `webhooks.stripe.refund` | Gateway | Normalizer |
| `webhooks.dlq` | Gateway | - |
| `payments.normalized` | Normalizer | Orchestrator |
| `payments.validation.dlq` | Normalizer | Orchestrator |

### Temporal Workflows

**PaymentEventWorkflow** (`src/orchestrator/workflows/payment_event.py`):
1. `validate_business_rules` - Final business rule validation
2. `get_fraud_score` - Call inference service (successful payments)
3. `get_retry_strategy` - Call inference service (failed payments)
4. `get_churn_prediction` - Call inference service for churn risk
5. `persist_to_postgres` - Write to PostgreSQL (Dagster batch ingests to Iceberg)

**DLQReviewWorkflow** (`src/orchestrator/workflows/dlq_review.py`):
- Persists quarantined events to PostgreSQL quarantine table

Workflows use `event_id` as workflow ID with `WorkflowIDConflictPolicy.USE_EXISTING` for idempotency.

### Inference Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /fraud/score` | Fraud probability scoring |
| `POST /retry/strategy` | Retry timing recommendations |
| `POST /churn/predict` | Customer churn prediction |
| `POST /recovery/recommend` | Failed payment recovery planning |

## Key Patterns

### Unified Event Schema

The normalizer transforms provider events to `UnifiedPaymentEvent`:

```python
event_id: str           # "stripe:evt_xxx"
provider: str           # "stripe"
event_type: str         # "payment.succeeded"
amount_cents: int       # Non-negative, max $1M
currency: str           # ISO 4217 (20 supported)
status: str
failure_code: str | None
```

### Validation Layers

1. **Gateway**: Signature verification (HMAC-SHA256), structure validation
2. **Normalizer**: Currency (ISO 4217), amount bounds (0-$1M), null normalization
3. **Orchestrator**: Business rules via Temporal activities

### Adding New Payment Providers

**Gateway** (`src/payment_gateway/providers/<provider>/`):
- `models.py` - Pydantic webhook models
- `validator.py` - Signature verification
- `router.py` - FastAPI routes
- Register in `main.py`

**Normalizer** (`src/normalizer/`):
- `transformers/<provider>.py` - Transform to unified schema
- `handlers/<provider>.py` - Process events
- Register in `main.py:_get_handler()`

## Design Decisions

**Python Normalizer (not Flink)**: Aligns with target tech stack (Python, Kafka, Temporal). Simpler deployment. Temporal best practices recommend validating upstream.

**Temporal for Orchestration**: Durable execution survives restarts. Event_id as workflow ID ensures idempotency. Per-activity retry policies.

**Mock Inference Service**: Demonstrates ML integration pattern. Deterministic scoring based on input features.
