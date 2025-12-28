# Temporal Worker Service

Temporal workflow service that processes normalized payment events, enriches them with ML inference, and persists to PostgreSQL.

## Architecture

```
Kafka (payments.normalized) --> Temporal Worker --> Temporal Workflows
                                                       |
                               +---------------------+-------------------+
                               |                     |                   |
                               v                     v                   v
                        Inference Service      Validation         PostgreSQL
                        (Fraud/Churn/Retry)                        (Bronze)
```

## Features

- Durable workflow execution (survives restarts)
- Event-based idempotency (event_id as workflow ID)
- Per-activity retry policies with exponential backoff
- ML inference enrichment (fraud score, churn prediction, retry strategy)
- DLQ handling for quarantined events

## Temporal Workflows

### PaymentEventWorkflow

Processes valid normalized events:

1. `validate_business_rules` - Final business rule validation
2. `get_fraud_score` - Fraud probability scoring (successful payments)
3. `get_retry_strategy` - Retry recommendations (failed payments)
4. `get_churn_prediction` - Customer churn risk
5. `persist_to_postgres` - Write enriched event to PostgreSQL

### DLQReviewWorkflow

Processes quarantined events:
- Persists to `payment_events_quarantine` table for manual review

## Running Locally

```bash
cd services/temporal
uv sync

# Requires Temporal server running
python -m temporal_worker.main
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TEMPORAL_WORKER_KAFKA_BOOTSTRAP_SERVERS` | Kafka broker | `localhost:9092` |
| `TEMPORAL_WORKER_TEMPORAL_HOST` | Temporal server | `localhost:7233` |
| `TEMPORAL_WORKER_INFERENCE_SERVICE_URL` | Inference service URL | `http://localhost:8002` |
| `TEMPORAL_WORKER_POSTGRES_HOST` | PostgreSQL host | `localhost` |
| `TEMPORAL_WORKER_POSTGRES_DB` | Database name | `payments` |

## Kafka Topics

**Input:**
- `payments.normalized` - Valid normalized events
- `payments.validation.dlq` - Quarantined events

## PostgreSQL Tables

| Table | Description |
|-------|-------------|
| `payment_events` | Enriched payment events |
| `payment_events_quarantine` | Failed validation events |

## Testing

```bash
uv run pytest tests/ -v
```

## Docker

Build and run with Docker Compose from project root:

```bash
make temporal-worker-up
```

## Idempotency

Workflows use `event_id` as the workflow ID with `WorkflowIDConflictPolicy.USE_EXISTING`, ensuring:
- Duplicate events don't create duplicate workflows
- Safe replay after failures
- Exactly-once processing semantics
