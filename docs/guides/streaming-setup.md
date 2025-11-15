# Streaming Data Lakehouse Setup Guide

This guide walks you through setting up a local streaming data lakehouse with Kafka, Flink, and Iceberg - inspired by real-world payment processing use cases.

## Overview

This setup demonstrates a complete streaming data pipeline:

```
Payment Events (JR) → Kafka → Flink → Iceberg (Polaris + MinIO) → Trino/Dagster
```

**Key Components:**
- **Apache Kafka**: Event streaming platform for payment events
- **Apache Flink**: Stream processing engine with Iceberg connector
- **Apache Polaris**: REST catalog for Iceberg table management
- **MinIO**: S3-compatible storage for Iceberg data files
- **Trino**: SQL query engine for analytics
- **Dagster**: Orchestration and metadata management
- **JR**: Data generator for realistic payment events

**Use Case:** Butter Payments-inspired payment processing pipeline that ingests, cleans, and normalizes payment events from multiple providers (Stripe, Braintree, Adyen, etc.) with built-in data quality challenges.

## Quick Start

### 1. Start the Streaming Stack

```bash
make docker-up
```

This starts all services:
- Kafka broker on `localhost:9092`
- Flink JobManager UI on `http://localhost:8081`
- Polaris REST catalog on `http://localhost:8181`
- MinIO console on `http://localhost:9001`
- Trino on `http://localhost:8080`
- Dagster on `http://localhost:3000`

### 2. Configure Flink Streaming Pipeline

Attach to the Flink SQL client:

```bash
docker compose -f infrastructure/docker/docker-compose.yml attach flink-sql-client
```

Inside the Flink SQL console, run these commands one at a time:

#### Create Kafka Source Catalog

```sql
CREATE CATALOG kafka_catalog WITH ('type'='generic_in_memory');
CREATE DATABASE kafka_catalog.payments_db;
```

#### Create Kafka Source Table (Payment Charges)

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
    failure_code STRING,
    failure_message STRING,
    payment_method_id STRING,
    payment_method_type STRING,
    card_brand STRING,
    card_last4 STRING,
    card_exp_month INT,
    card_exp_year INT,
    card_country STRING,
    billing_country STRING,
    billing_postal_code STRING,
    merchant_id STRING,
    merchant_name STRING,
    description STRING,
    metadata ROW<
        order_id STRING,
        user_email STRING,
        subscription_id STRING
    >,
    risk_score INT,
    risk_level STRING,
    `3ds_authenticated` STRING,
    created_at TIMESTAMP(3),
    updated_at TIMESTAMP(3),
    WATERMARK FOR created_at AS created_at - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'properties.bootstrap.servers' = 'kafka-broker:29092',
    'format' = 'json',
    'scan.startup.mode' = 'earliest-offset',
    'topic' = 'payment_charges'
);
```

#### Create Polaris (Iceberg) Catalog

```sql
CREATE CATALOG polaris_catalog WITH (
    'type'='iceberg',
    'catalog-type'='rest',
    'uri'='http://polaris:8181/api/catalog',
    'warehouse'='polariscatalog',
    'oauth2-server-uri'='http://polaris:8181/api/catalog/v1/oauth/tokens',
    'credential'='root:secret',
    'scope'='PRINCIPAL_ROLE:ALL'
);
```

#### Create Database in Polaris

```sql
CREATE DATABASE polaris_catalog.payments_db;
```

#### Enable Checkpointing (Required for Iceberg Sink)

```sql
SET 'execution.checkpointing.interval' = '10s';
```

#### Create Streaming Sink (Kafka → Iceberg)

This creates a dynamic table that continuously streams data from Kafka to Iceberg:

```sql
CREATE TABLE polaris_catalog.payments_db.payment_charges AS
    SELECT * FROM kafka_catalog.payments_db.payment_charges;
```

### 3. Generate Payment Events

In a separate terminal, start generating payment events:

#### Single Event Type

```bash
# Generate charge events (500ms frequency)
make jr-charges

# Or refunds (2s frequency)
make jr-refunds

# Or disputes (5s frequency)
make jr-disputes

# Or subscriptions (3s frequency)
make jr-subscriptions
```

#### All Event Types Simultaneously

```bash
make jr-all
```

This runs all generators in the background. Logs are written to `/tmp/jr-*.log`.

Stop all generators:

```bash
make jr-stop
```

### 4. Query Streaming Data

#### From Flink SQL Client

```sql
-- Check data is flowing (run multiple times to see count increase)
SELECT COUNT(*) FROM polaris_catalog.payments_db.payment_charges;

-- View recent charges
SELECT
    charge_id,
    customer_id,
    amount,
    currency,
    status,
    provider,
    created_at
FROM polaris_catalog.payments_db.payment_charges
ORDER BY created_at DESC
LIMIT 10;
```

#### From Trino

```bash
# Connect to Trino
docker compose -f infrastructure/docker/docker-compose.yml exec -it trino trino --server localhost:8080 --catalog iceberg
```

```sql
-- Analytics queries
SELECT
    provider,
    status,
    COUNT(*) as transaction_count,
    AVG(amount) as avg_amount,
    SUM(amount) as total_amount
FROM payments_db.payment_charges
GROUP BY provider, status
ORDER BY total_amount DESC;

-- Data quality checks (find problematic records)
SELECT
    card_country,
    COUNT(*) as count
FROM payments_db.payment_charges
WHERE card_country NOT IN ('US', 'CA', 'GB', 'FR', 'DE', 'AU')
GROUP BY card_country
ORDER BY count DESC;
```

## Payment Event Templates

The project includes four Stripe-like payment event types with built-in data quality challenges:

### 1. Payment Charges (`payment_charge.json`)

**Topic:** `payment_charges`
**Frequency:** 500ms
**Fields:**
- Transaction details (charge_id, amount, currency, status)
- Payment method information (type, card details)
- Merchant information
- Risk scoring (0-100)
- Metadata (order_id, user_email, subscription_id)

**Data Quality Issues:**
- null vs NULL vs 'null' variations
- Invalid country codes (e.g., "342", "999")
- Missing postal codes
- Mixed case currencies (usd, EUR, gbp)

### 2. Payment Refunds (`payment_refund.json`)

**Topic:** `payment_refunds`
**Frequency:** 2s
**Fields:**
- Refund details (refund_id, charge_id, amount)
- Refund reason and status
- Support ticket references
- Failure reasons

**Data Quality Issues:**
- Null status fields
- Inconsistent reason formats
- Missing support ticket IDs

### 3. Payment Disputes (`payment_dispute.json`)

**Topic:** `payment_disputes`
**Frequency:** 5s
**Fields:**
- Dispute details (dispute_id, charge_id, amount)
- Reason codes (network and internal)
- Evidence tracking
- Status workflow

**Data Quality Issues:**
- Missing evidence metadata
- Null currency fields
- Incomplete case numbers

### 4. Subscription Events (`payment_subscription.json`)

**Topic:** `payment_subscriptions`
**Frequency:** 3s
**Fields:**
- Subscription lifecycle (created, updated, canceled)
- Plan information
- Trial periods
- Discount/coupon tracking

**Data Quality Issues:**
- Null trial dates
- Missing promo codes
- Inconsistent interval formats

## Real-World Use Case: Butter Payments

This setup is inspired by [Butter Payments' Data Engineering role](https://jobs.lever.co/ButterPayments/4d9ae20b-5a36-4e61-acfe-33881896fbc0), which focuses on:

1. **Multi-Provider Ingestion**: Events from Stripe, Braintree, Adyen, etc.
2. **Data Normalization**: Standardizing schemas across providers
3. **Data Quality Validation**: Detecting nulls, invalid codes, malformed data
4. **Transformation Layers**: Cleaning data as far upstream as possible
5. **ML Pipeline Support**: Preparing data for machine learning models

**Challenges to Practice:**

- **Schema Standardization**: Create DBT models to normalize across providers
- **Data Quality Tests**: Write Flink/DBT tests for validation rules
- **Deduplication**: Handle duplicate payment events
- **Enrichment**: Join payment events with customer/merchant data
- **SCD Type 2**: Track subscription status changes over time

## Advanced Flink Pipeline Configurations

### Multiple Source Tables

Create tables for all event types:

```sql
-- Refunds table
CREATE TABLE kafka_catalog.payments_db.payment_refunds (
    event_id STRING,
    event_type STRING,
    provider STRING,
    refund_id STRING,
    charge_id STRING,
    customer_id STRING,
    amount DECIMAL(10, 2),
    currency STRING,
    status STRING,
    reason STRING,
    failure_reason STRING,
    merchant_id STRING,
    metadata ROW<
        refund_requested_by STRING,
        original_order_id STRING,
        support_ticket_id STRING
    >,
    created_at TIMESTAMP(3),
    updated_at TIMESTAMP(3),
    WATERMARK FOR created_at AS created_at - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'properties.bootstrap.servers' = 'kafka-broker:29092',
    'format' = 'json',
    'scan.startup.mode' = 'earliest-offset',
    'topic' = 'payment_refunds'
);

-- Create Iceberg sink
CREATE TABLE polaris_catalog.payments_db.payment_refunds AS
    SELECT * FROM kafka_catalog.payments_db.payment_refunds;
```

### Transformation Pipeline

Apply transformations before writing to Iceberg:

```sql
-- Data quality transformation
CREATE TABLE polaris_catalog.payments_db.payment_charges_cleaned AS
SELECT
    event_id,
    event_type,
    UPPER(provider) as provider,  -- Normalize provider names
    charge_id,
    customer_id,
    amount,
    UPPER(currency) as currency,  -- Standardize currency codes
    status,
    -- Convert various null representations to actual NULL
    CASE
        WHEN failure_code IN ('null', 'NULL', '') THEN NULL
        ELSE failure_code
    END as failure_code,
    -- Validate country codes (only allow valid 2-letter codes)
    CASE
        WHEN card_country ~ '^[A-Z]{2}$' THEN card_country
        ELSE NULL
    END as card_country,
    risk_score,
    risk_level,
    created_at,
    updated_at
FROM kafka_catalog.payments_db.payment_charges;
```

## Monitoring & Debugging

### View Flink Jobs

Open Flink Web UI: `http://localhost:8081`

- Running Jobs
- Task Managers
- Checkpoints
- Metrics

### Check Kafka Topics

```bash
# List all topics
docker compose -f infrastructure/docker/docker-compose.yml exec kafka-broker \
  kafka-topics.sh --list --bootstrap-server localhost:9092

# Describe a topic
docker compose -f infrastructure/docker/docker-compose.yml exec kafka-broker \
  kafka-topics.sh --describe --topic payment_charges --bootstrap-server localhost:9092

# Consume messages (from beginning)
docker compose -f infrastructure/docker/docker-compose.yml exec kafka-broker \
  kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic payment_charges \
  --from-beginning \
  --max-messages 10
```

### View Iceberg Files in MinIO

1. Open MinIO console: `http://localhost:9001`
2. Login: `admin` / `password`
3. Browse bucket: `warehouse/`
4. Navigate to: `warehouse/polariscatalog/payments_db/payment_charges/`

You'll see:
- `metadata/` - Table metadata (JSON)
- `data/` - Parquet data files

### Check Polaris Catalog

```bash
# Test catalog API
curl http://localhost:8181/api/catalog/v1/config | jq '.'

# Get OAuth token
curl -s http://localhost:8181/api/catalog/v1/oauth/tokens \
  --user "root:secret" \
  -d 'grant_type=client_credentials' \
  -d 'scope=PRINCIPAL_ROLE:ALL' | jq '.access_token'
```

## Troubleshooting

### JR Tool Not Found

```bash
# Install JR
brew install jr

# Fix configuration (important!)
rm /opt/homebrew/etc/jr/jrconfig.json
```

Without removing the default config, JR uses JSON Schema format which conflicts with our Kafka setup.

### Flink Can't Write to Iceberg

**Error:** "Iceberg sink requires checkpointing"

**Solution:** Enable checkpointing in Flink SQL:

```sql
SET 'execution.checkpointing.interval' = '10s';
```

### Kafka Connection Refused

**Error:** "Connection to kafka-broker:29092 refused"

**Solution:** Make sure you're using the internal broker address:
- Inside Docker network: `kafka-broker:29092`
- From host machine: `localhost:9092`

Update JR config if needed: `infrastructure/docker/jr/kafka.client.properties`

### Polaris Authentication Failed

**Error:** "401 Unauthorized"

**Default credentials:**
- Client ID: `root`
- Client Secret: `secret`

These are set in [docker-compose.yml](docker-compose.yml:14):
```yaml
POLARIS_BOOTSTRAP_CREDENTIALS: default-realm,root,secret
```

## Next Steps

### Integration with Dagster

1. Create Dagster assets that read from Iceberg tables
2. Build transformation jobs (DBT models)
3. Schedule data quality checks
4. Materialize feature tables for ML

### DBT Transformations

Create DBT models in `transformations/dbt/models/`:

```sql
-- staging/stg_payment_charges.sql
WITH source AS (
    SELECT * FROM {{ source('raw', 'payment_charges') }}
)
SELECT
    charge_id,
    customer_id,
    UPPER(currency) as currency,
    -- Data quality transformations
    CASE WHEN failure_code IN ('null', 'NULL') THEN NULL
         ELSE failure_code
    END as failure_code,
    created_at
FROM source
```

### ML Feature Engineering

Use Flink for real-time feature computation:

```sql
-- Rolling aggregates for fraud detection
SELECT
    customer_id,
    COUNT(*) OVER w as transactions_1h,
    SUM(amount) OVER w as total_amount_1h,
    AVG(risk_score) OVER w as avg_risk_1h
FROM kafka_catalog.payments_db.payment_charges
WINDOW w AS (
    PARTITION BY customer_id
    ORDER BY created_at
    RANGE BETWEEN INTERVAL '1' HOUR PRECEDING AND CURRENT ROW
);
```

## References

- [Blog Post: Streaming Data Lakehouse with Flink and Iceberg](https://blog.det.life/streaming-data-lakehouse-part-2-flink-kafka-and-jr-for-real-time-ingestion-4dcd5dba8bbc)
- [Butter Payments Data Engineering Role](https://jobs.lever.co/ButterPayments/4d9ae20b-5a36-4e61-acfe-33881896fbc0)
- [Apache Flink Iceberg Connector](https://iceberg.apache.org/docs/latest/flink/)
- [JR Data Generator](https://github.com/ugol/jr)
- [Apache Polaris REST Catalog](https://polaris.apache.org/)

## Makefile Command Reference

```bash
# Docker Compose
make docker-up              # Start all services
make docker-down            # Stop all services
make docker-build           # Rebuild images
make docker-restart         # Restart services
make docker-status          # Show service status
make docker-logs            # View logs

# JR Data Generation
make jr-charges             # Generate charge events
make jr-refunds             # Generate refund events
make jr-disputes            # Generate dispute events
make jr-subscriptions       # Generate subscription events
make jr-all                 # Generate all event types
make jr-stop                # Stop all generators
make jr-help                # Show installation help
```
