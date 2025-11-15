# JR Payment Event Templates

This directory contains JR templates for generating realistic Stripe-like payment events. These templates are inspired by the [Butter Payments Data Engineering role](https://jobs.lever.co/ButterPayments/4d9ae20b-5a36-4e61-acfe-33881896fbc0) and include built-in data quality challenges for testing transformation and validation pipelines.

## Templates

### 1. payment_charge.json

**Kafka Topic:** `payment_charges`
**Recommended Frequency:** 500ms

Generates charge events representing successful and failed payment transactions.

**Key Features:**
- Multiple payment providers (Stripe, Braintree, Adyen, Checkout, Square)
- Card payment details (brand, last4, expiration, country)
- Risk scoring (0-100)
- 3D Secure authentication status
- Nested metadata (order_id, user_email, subscription_id)

**Data Quality Challenges:**
- `null` vs `NULL` vs empty string variations
- Invalid country codes (342, 999)
- Mixed-case currency codes (usd, EUR, gbp)
- Missing billing information

**Usage:**
```bash
make jr-charges

# Or manually:
jr run \
  --embedded "$(cat payment_charge.json)" \
  --num 0 \
  --frequency 500ms \
  --output kafka \
  --topic payment_charges \
  --kafkaConfig kafka.client.properties
```

### 2. payment_refund.json

**Kafka Topic:** `payment_refunds`
**Recommended Frequency:** 2s

Generates refund events for previously charged transactions.

**Key Features:**
- Refund lifecycle (created, succeeded, failed)
- Reason tracking (customer request, fraud, duplicate)
- Links to original charge_id
- Support ticket references

**Data Quality Challenges:**
- Null status fields
- Missing refund reasons
- Incomplete support ticket IDs

**Usage:**
```bash
make jr-refunds
```

### 3. payment_dispute.json

**Kafka Topic:** `payment_disputes`
**Recommended Frequency:** 5s

Generates dispute/chargeback events.

**Key Features:**
- Dispute workflow (created, updated, closed)
- Network reason codes (4853, 4834, 4863)
- Evidence tracking metadata
- Win/loss outcomes

**Data Quality Challenges:**
- Null currency fields
- Missing case numbers
- Incomplete evidence metadata

**Usage:**
```bash
make jr-disputes
```

### 4. payment_subscription.json

**Kafka Topic:** `payment_subscriptions`
**Recommended Frequency:** 3s

Generates subscription lifecycle events.

**Key Features:**
- Multiple subscription states (active, past_due, canceled, trialing)
- Plan information (interval, interval_count, amount)
- Trial period tracking
- Discount/coupon application

**Data Quality Challenges:**
- Null trial dates
- Missing promo codes
- Inconsistent interval formats (month, year, week)

**Usage:**
```bash
make jr-subscriptions
```

## Running All Generators

Generate all event types simultaneously:

```bash
make jr-all
```

This runs all generators in the background with different frequencies to simulate a realistic payment processing environment. Logs are written to `/tmp/jr-*.log`.

Stop all generators:

```bash
make jr-stop
```

## Data Quality Testing

These templates are designed to test your data transformation and validation logic:

### Common Data Quality Issues

1. **Null Handling**: Multiple representations (null, NULL, '', 'null')
   ```sql
   -- Flink transformation
   CASE
       WHEN failure_code IN ('null', 'NULL', '') THEN NULL
       ELSE failure_code
   END as failure_code
   ```

2. **Country Code Validation**: Invalid codes like 342, 999
   ```sql
   -- Validation rule
   CASE
       WHEN card_country ~ '^[A-Z]{2}$' THEN card_country
       ELSE NULL
   END as card_country
   ```

3. **Currency Normalization**: Mixed case (usd, EUR, gbp)
   ```sql
   -- Standardization
   UPPER(currency) as currency
   ```

4. **Provider Normalization**: Consistent naming
   ```sql
   -- Normalize provider names
   CASE
       WHEN LOWER(provider) = 'stripe' THEN 'STRIPE'
       WHEN LOWER(provider) = 'braintree' THEN 'BRAINTREE'
       ELSE UPPER(provider)
   END as provider
   ```

## Configuration

### kafka.client.properties

```properties
bootstrap.servers=localhost:9092
```

**Important:** This uses `localhost:9092` because JR runs on the host machine. Inside Docker containers, use `kafka-broker:29092`.

## Installation

### Install JR

```bash
brew install jr
```

### Fix Default Configuration

After installing JR via Homebrew, delete the default config to prevent JSON Schema format conflicts:

```bash
rm /opt/homebrew/etc/jr/jrconfig.json
```

## Customization

### Adjust Event Frequency

```bash
jr run \
  --embedded "$(cat payment_charge.json)" \
  --num 0 \
  --frequency 1s \  # Changed from 500ms
  --output kafka \
  --topic payment_charges \
  --kafkaConfig kafka.client.properties
```

### Generate Fixed Number of Events

```bash
jr run \
  --embedded "$(cat payment_charge.json)" \
  --num 100 \  # Generate exactly 100 events, then stop
  --frequency 500ms \
  --output kafka \
  --topic payment_charges \
  --kafkaConfig kafka.client.properties
```

### Add Custom Fields

Edit the JSON templates to add or modify fields. JR supports:

- `{{key "prefix" max}}` - Unique incrementing keys
- `{{randoms "opt1|opt2|opt3"}}` - Random selection
- `{{integer min max}}` - Random integers
- `{{amount min max ""}}` - Random decimal amounts
- `{{email}}` - Random email addresses
- `{{format_timestamp now "layout"}}` - Timestamps

See [JR documentation](https://github.com/ugol/jr) for full template syntax.

## Example: Stripe Charge Event

```json
{
  "event_id": "evt_123456",
  "event_type": "charge.succeeded",
  "provider": "stripe",
  "charge_id": "ch_789012",
  "customer_id": "cus_345678",
  "amount": 45.99,
  "currency": "usd",
  "status": "succeeded",
  "failure_code": "null",
  "payment_method_id": "pm_901234",
  "card_brand": "visa",
  "card_last4": "4242",
  "card_country": "US",
  "risk_score": 25,
  "created_at": "2025-01-13T12:34:56Z"
}
```

## Integration with Flink

After generating events, create Kafka source tables in Flink SQL:

```sql
CREATE TABLE kafka_catalog.payments_db.payment_charges (
    event_id STRING,
    event_type STRING,
    provider STRING,
    charge_id STRING,
    customer_id STRING,
    amount DECIMAL(10, 2),
    currency STRING,
    status STRING,
    -- ... other fields
    created_at TIMESTAMP(3),
    WATERMARK FOR created_at AS created_at - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'properties.bootstrap.servers' = 'kafka-broker:29092',
    'format' = 'json',
    'topic' = 'payment_charges'
);
```

See [STREAMING_SETUP.md](../STREAMING_SETUP.md) for complete Flink pipeline configuration.

## References

- [JR GitHub Repository](https://github.com/ugol/jr)
- [Butter Payments Job Description](https://jobs.lever.co/ButterPayments/4d9ae20b-5a36-4e61-acfe-33881896fbc0)
- [Streaming Data Lakehouse Blog](https://blog.det.life/streaming-data-lakehouse-part-2-flink-kafka-and-jr-for-real-time-ingestion-4dcd5dba8bbc)
