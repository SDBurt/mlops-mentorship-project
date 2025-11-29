# Payment Pipeline

End-to-end payment event processing pipeline with webhook ingestion, validation, and normalization.

## Overview

This project implements the payment processing pipeline:

| System | Component | Description |
|--------|-----------|-------------|
| **System 1** | Gateway | Receives webhooks, verifies signatures, publishes to Kafka |
| **System 2** | Normalizer | Validates events, transforms to unified schema, routes to DLQ |
| **System 3** | Orchestrator | Temporal workflows for ML inference and PostgreSQL persistence |
| **Support** | Inference | Mock ML service for fraud, retry, churn predictions |

## Architecture

```
Payment Provider (Stripe)
         |
         v
+------------------+     +-------------------+     +------------------+     +------------+
|     Gateway      | --> |    Normalizer     | --> |   Orchestrator   | --> | PostgreSQL |
|    (FastAPI)     |     | (Kafka Consumer)  |     |    (Temporal)    |     |            |
+------------------+     +-------------------+     +------------------+     +------------+
         |                        |                        |                      |
         v                        v                        v                      v
  webhooks.stripe.*        payments.normalized      Inference Service      Dagster Batch
                           payments.validation.dlq  (Fraud/Retry/Churn)          |
                                                                                 v
                                                                           Iceberg Lake
```

## Quick Start

### Using Make (Recommended)

```bash
# From the kubernetes/ directory

# Start gateway + normalizer
make normalizer-up

# Start webhook simulator
make gateway-simulator

# View normalizer logs
make normalizer-logs

# Check message counts
make normalizer-counts
```

### Local Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the gateway
uvicorn payment_gateway.main:app --reload --port 8000

# Run the normalizer (requires Kafka)
python -m normalizer.main
```

### Docker Compose

```bash
# From infrastructure/docker directory
docker compose --profile gateway --profile normalizer up -d
```

---

## System 1: Gateway

The gateway receives HTTP webhooks from payment providers, verifies signatures, and publishes to Kafka.

### Features

- HMAC-SHA256 signature verification
- Pydantic v2 models with discriminated unions
- Per-event-type Kafka topics
- Dead letter queue for invalid payloads
- Retry logic with exponential backoff

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/webhooks/stripe/` | POST | Stripe webhook receiver |

### Gateway Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka-broker:29092` | Kafka bootstrap servers |
| `STRIPE_WEBHOOK_SECRET` | Required | Stripe webhook signing secret |
| `LOG_LEVEL` | `INFO` | Log level |

---

## System 2: Normalizer

The normalizer consumes raw webhook events, validates content, transforms to a unified schema, and routes invalid events to a DLQ.

### Features

- ISO 4217 currency validation (20 supported currencies)
- Amount bounds checking (0 to $1M)
- Null string normalization ("null", "", "None" -> None)
- Provider-agnostic unified event schema
- Structured DLQ payloads with error details

### Unified Event Schema

```python
UnifiedPaymentEvent:
    event_id: str           # "stripe:evt_xxx"
    provider: str           # "stripe"
    provider_event_id: str  # "evt_xxx"
    event_type: str         # "payment.succeeded" (normalized)
    merchant_id: str | None
    customer_id: str | None
    amount_cents: int       # Non-negative
    currency: str           # Uppercase ISO 4217
    payment_method_type: str | None
    card_brand: str | None
    card_last_four: str | None
    status: str
    failure_code: str | None
    failure_message: str | None
    metadata: dict
    provider_created_at: datetime
    processed_at: datetime
    schema_version: int     # 1
```

### Normalizer Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NORMALIZER_KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka bootstrap servers |
| `NORMALIZER_KAFKA_CONSUMER_GROUP` | `normalizer-group` | Consumer group ID |
| `NORMALIZER_INPUT_TOPICS` | See below | Comma-separated input topics |
| `NORMALIZER_OUTPUT_TOPIC` | `payments.normalized` | Normalized events topic |
| `NORMALIZER_DLQ_TOPIC` | `payments.validation.dlq` | Dead letter queue topic |
| `NORMALIZER_LOG_LEVEL` | `INFO` | Log level |

Default input topics: `webhooks.stripe.payment_intent,webhooks.stripe.charge,webhooks.stripe.refund`

### Validation Error Codes

| Code | Description |
|------|-------------|
| `INVALID_JSON` | Payload is not valid JSON |
| `MISSING_EVENT_ID` | Event ID is required |
| `MISSING_EVENT_TYPE` | Event type is required |
| `MISSING_DATA_OBJECT` | data.object is required |
| `MISSING_OBJECT_ID` | data.object.id is required |
| `INVALID_AMOUNT` | Amount is missing or invalid |
| `INVALID_AMOUNT_NEGATIVE` | Amount cannot be negative |
| `INVALID_AMOUNT_TOO_LARGE` | Amount exceeds maximum ($1M) |
| `INVALID_CURRENCY` | Currency is missing or unsupported |

---

## Kafka Topics

| Topic | Producer | Consumer | Description |
|-------|----------|----------|-------------|
| `webhooks.stripe.payment_intent` | Gateway | Normalizer | Raw payment intent events |
| `webhooks.stripe.charge` | Gateway | Normalizer | Raw charge events |
| `webhooks.stripe.refund` | Gateway | Normalizer | Raw refund events |
| `webhooks.dlq` | Gateway | - | Gateway validation failures |
| `payments.normalized` | Normalizer | Temporal | Normalized payment events |
| `payments.validation.dlq` | Normalizer | - | Normalizer validation failures |

---

## Simulator CLI

```bash
# Send single webhook
python -m simulator.main send --type payment_intent.succeeded

# Generate continuous traffic
python -m simulator.main generate --rate 5 --duration 60

# Test invalid signature (for DLQ testing)
python -m simulator.main send --type payment_intent.succeeded --invalid-signature
```

---

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=payment_gateway --cov=normalizer

# Run only unit tests
pytest tests/unit/

# Run normalizer tests only
pytest tests/unit/test_normalizer_*.py -v
```

---

## Project Structure

```
payment-pipeline/
├── src/
│   ├── payment_gateway/       # System 1: Gateway
│   │   ├── main.py           # FastAPI app
│   │   ├── core/             # Exceptions, config
│   │   └── providers/
│   │       └── stripe/       # Stripe models, validator, router
│   │
│   ├── normalizer/           # System 2: Normalizer
│   │   ├── main.py           # Kafka consumer loop
│   │   ├── config.py         # Settings
│   │   ├── validators/       # Currency, amount, null validation
│   │   ├── transformers/     # UnifiedPaymentEvent, StripeTransformer
│   │   └── handlers/         # StripeHandler
│   │
│   └── orchestrator/         # System 3: Orchestrator
│       ├── main.py           # Kafka-Temporal bridge
│       ├── consumer.py       # Kafka consumer
│       ├── workflows/        # PaymentEventWorkflow, DLQReviewWorkflow
│       └── activities/       # Validation, fraud, retry, churn, postgres
│
├── inference_service/        # Support: Mock ML Service
│   ├── main.py              # FastAPI app
│   └── routes/              # fraud, retry, churn, recovery endpoints
│
├── simulator/                # Webhook simulator CLI
├── tests/
│   ├── unit/
│   │   ├── test_stripe_*.py           # Gateway tests
│   │   ├── test_normalizer_*.py       # Normalizer tests
│   │   ├── test_orchestrator_*.py     # Orchestrator tests
│   │   └── test_inference_*.py        # Inference tests
│   └── integration/
├── Dockerfile                # Gateway image
├── Dockerfile.normalizer     # Normalizer image
├── Dockerfile.orchestrator   # Orchestrator image
├── Dockerfile.inference      # Inference service image
└── pyproject.toml
```

---

## Adding New Providers

### Gateway

1. Create `src/payment_gateway/providers/<provider>/` directory
2. Implement provider-specific Pydantic models in `models.py`
3. Implement signature verification in `validator.py`
4. Create FastAPI router in `router.py`
5. Register router in `main.py`

### Normalizer

1. Create `src/normalizer/transformers/<provider>.py`
2. Implement `<Provider>Transformer` class with `transform()` method
3. Create `src/normalizer/handlers/<provider>.py`
4. Implement `<Provider>Handler` class with `process()` method
5. Register handler in `main.py:_get_handler()`
