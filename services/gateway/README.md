# Payment Gateway Service

Webhook ingestion service that receives payment events from providers (Stripe, Square, Adyen, Braintree), validates signatures, and publishes to Kafka.

## Architecture

```
Provider Webhooks --> Gateway (FastAPI) --> Kafka Topics
                          |
                       [DLQ]
```

## Features

- HMAC-SHA256 signature verification per provider
- Provider-specific webhook parsing
- Kafka producer with async publishing
- Dead letter queue for malformed payloads
- Health check endpoint

## Supported Providers

| Provider | Endpoint | Signature Method |
|----------|----------|------------------|
| Stripe | `/webhooks/stripe/` | HMAC-SHA256 with timestamp |
| Square | `/webhooks/square/` | HMAC-SHA256 |
| Adyen | `/webhooks/adyen/` | HMAC-SHA256 (Base64) |
| Braintree | `/webhooks/braintree/` | XML signature verification |

## Running Locally

```bash
cd services/gateway
uv sync
uvicorn payment_gateway.entrypoints.stripe_main:app --reload --port 8000
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker address | `localhost:9092` |
| `STRIPE_WEBHOOK_SECRET` | Stripe signing secret | - |
| `SQUARE_WEBHOOK_SIGNATURE_KEY` | Square signing key | - |
| `ADYEN_HMAC_KEY` | Adyen HMAC key | - |
| `BRAINTREE_MERCHANT_ID` | Braintree merchant ID | - |

## Kafka Topics

| Topic | Description |
|-------|-------------|
| `webhooks.stripe.payment_intent` | Stripe payment intent events |
| `webhooks.stripe.charge` | Stripe charge events |
| `webhooks.stripe.refund` | Stripe refund events |
| `webhooks.dlq` | Dead letter queue |

## Testing

```bash
uv run pytest tests/ -v
```

## Docker

Build and run with Docker Compose from project root:

```bash
make gateway-up
```

Or build individually:

```bash
docker build -f services/gateway/docker/Dockerfile.stripe -t stripe-gateway:latest ../..
```
