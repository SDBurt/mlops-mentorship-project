# ML Inference Service

FastAPI service providing real-time ML predictions for payment processing, including fraud scoring, churn prediction, and retry strategy recommendations.

## Architecture

```
Orchestrator --> Inference Service --> Feast (Features)
                      |                    |
                      v                    v
                 MLflow (Models)      Redis (Online Store)
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/fraud/score` | POST | Fraud probability scoring |
| `/retry/strategy` | POST | Retry timing recommendations |
| `/churn/predict` | POST | Customer churn prediction |
| `/recovery/recommend` | POST | Failed payment recovery planning |

## API Examples

### Fraud Scoring

```bash
curl -X POST http://localhost:8002/fraud/score \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_123",
    "amount_cents": 50000,
    "currency": "usd",
    "customer_id": "cus_abc",
    "merchant_id": "mer_xyz"
  }'
```

Response:
```json
{
  "event_id": "evt_123",
  "fraud_score": 0.15,
  "risk_level": "low",
  "model_version": "1.0.0"
}
```

### Retry Strategy

```bash
curl -X POST http://localhost:8002/retry/strategy \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_456",
    "failure_code": "insufficient_funds",
    "attempt_count": 1
  }'
```

Response:
```json
{
  "event_id": "evt_456",
  "action": "retry",
  "delay_seconds": 3600,
  "max_attempts": 3,
  "reason": "Temporary failure - retry recommended"
}
```

## Running Locally

```bash
cd services/inference
uv sync
uvicorn inference_service.main:app --reload --port 8002
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `INFERENCE_HOST` | Service host | `0.0.0.0` |
| `INFERENCE_PORT` | Service port | `8002` |
| `FEAST_FEATURE_SERVER_URL` | Feast server URL | `http://localhost:6566` |
| `MLFLOW_TRACKING_URI` | MLflow server URL | `http://localhost:5001` |

## Models

| Model | Purpose | Features |
|-------|---------|----------|
| Fraud Detector | Identify fraudulent transactions | Amount, velocity, customer history |
| Churn Predictor | Predict customer churn risk | Payment history, failure rate |
| Retry Optimizer | Recommend retry strategy | Failure code, attempt count |

## Testing

```bash
uv run pytest tests/ -v
```

## Docker

Build and run with Docker Compose from project root:

```bash
make mlops-up
```

Or build individually:

```bash
docker build -f services/inference/docker/Dockerfile -t inference-service:latest ../..
```

## Integration

The inference service is called by the Orchestrator during payment processing:

1. Successful payments: Fraud scoring + churn prediction
2. Failed payments: Retry strategy recommendation
3. All predictions are persisted with the payment event in PostgreSQL
