# Payment Gateway

Webhook gateway service for receiving, validating, and publishing payment provider webhooks to Kafka.

## Overview

This service is part of the payment pipeline architecture (System 1 - Gateway). It:

1. Receives HTTP POST webhooks from payment providers (starting with Stripe)
2. Verifies webhook signatures (HMAC-SHA256)
3. Validates payload structure using Pydantic models
4. Publishes valid events to provider-specific Kafka topics
5. Routes invalid payloads to a dead letter queue (DLQ)

## Architecture

```
Payment Provider --> Gateway (FastAPI) --> Kafka Topics
       |                   |
       |                   +--> webhooks.stripe.payment_intent
       |                   +--> webhooks.stripe.charge
       |                   +--> webhooks.dlq (invalid payloads)
       |
Simulator (for testing)
```

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the gateway
uvicorn payment_gateway.main:app --reload --port 8000

# In another terminal, send a test webhook
python -m simulator.main send --type payment_intent.succeeded
```

### Docker

```bash
# From infrastructure/docker directory
docker compose up payment-gateway

# With simulator
docker compose --profile simulator up
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/webhooks/stripe/` | POST | Stripe webhook receiver |

## Kafka Topics

| Topic | Description |
|-------|-------------|
| `webhooks.stripe.payment_intent` | Payment intent events |
| `webhooks.stripe.charge` | Charge events |
| `webhooks.stripe.refund` | Refund events |
| `webhooks.dlq` | Invalid payloads |

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka-broker:29092` | Kafka bootstrap servers |
| `STRIPE_WEBHOOK_SECRET` | Required | Stripe webhook signing secret |
| `DEBUG` | `false` | Enable debug mode |

## Simulator CLI

```bash
# Send single webhook
python -m simulator.main send --type payment_intent.succeeded

# Generate continuous traffic
python -m simulator.main generate --rate 5 --duration 60

# Test invalid signature (for DLQ testing)
python -m simulator.main send --type payment_intent.succeeded --invalid-signature
```

## Adding New Providers

1. Create `src/payment_gateway/providers/<provider>/` directory
2. Implement provider-specific Pydantic models in `models.py`
3. Implement signature verification in `validator.py`
4. Create FastAPI router in `router.py`
5. Register router in `main.py`
6. Add Kafka topics configuration

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=payment_gateway

# Run only unit tests
pytest tests/unit/
```
