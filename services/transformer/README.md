# Payment Transformer Service

Kafka consumer that validates and transforms provider-specific webhook events into a unified payment event schema.

## Architecture

```
Kafka (webhooks.*) --> Transformer --> Kafka (payments.normalized)
                           |
                        [DLQ]
```

## Features

- ISO 4217 currency validation (20 supported currencies)
- Amount bounds validation (0 to $1M)
- Null value normalization
- Unified event schema transformation
- Dead letter queue for validation failures

## Unified Event Schema

```python
class UnifiedPaymentEvent:
    event_id: str           # "stripe:evt_xxx"
    provider: str           # "stripe", "square", etc.
    event_type: str         # "payment.succeeded", "payment.failed"
    amount_cents: int       # Non-negative, max 100,000,000
    currency: str           # ISO 4217 (usd, eur, gbp, etc.)
    status: str             # "succeeded", "failed", "pending"
    failure_code: str | None
    customer_id: str | None
    merchant_id: str | None
    metadata: dict
    created_at: datetime
    processed_at: datetime
```

## Running Locally

```bash
cd services/transformer
uv sync
python -m transformer.entrypoints.stripe_main
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TRANSFORMER_KAFKA_BOOTSTRAP_SERVERS` | Kafka broker address | `localhost:9092` |
| `TRANSFORMER_CONSUMER_GROUP` | Kafka consumer group | `transformer-group` |

## Kafka Topics

**Input:**
- `webhooks.stripe.payment_intent`
- `webhooks.stripe.charge`
- `webhooks.stripe.refund`
- `webhooks.square.*`
- `webhooks.adyen.*`
- `webhooks.braintree.*`

**Output:**
- `payments.normalized` - Valid normalized events
- `payments.validation.dlq` - Failed validation events

## Validation Rules

| Rule | Description |
|------|-------------|
| Currency | Must be valid ISO 4217 code |
| Amount | 0 <= amount <= 100,000,000 cents |
| Nulls | Empty strings converted to None |

## Testing

```bash
uv run pytest tests/ -v
```

## Docker

Build and run with Docker Compose from project root:

```bash
make transformer-up
```
