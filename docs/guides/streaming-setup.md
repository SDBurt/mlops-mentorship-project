# Streaming Data Lakehouse Setup Guide

This guide walks you through setting up a local streaming data lakehouse with Kafka, Flink, and Iceberg - inspired by real-world payment processing use cases.

## Overview

This setup demonstrates a complete streaming data pipeline:

```text
Payment Events (JR) → Kafka → Flink → Iceberg (Polaris + MinIO) → Trino/Dagster
```

**Key Components:**

- **Apache Kafka**: Event streaming platform for payment events
- **Apache Flink**: Stream processing engine with Iceberg connector
- **Apache Polaris**: REST catalog for Iceberg table management
- **MinIO**: S3-compatible storage for Iceberg data files
- **Trino**: SQL query engine for analytics
- **Dagster**: Orchestration and metadata management
- **JR**: Data generator for realistic payment events (charges, refunds, disputes, subscriptions)

**Use Case:** Butter Payments-inspired payment processing pipeline that ingests, cleans, and normalizes payment events from multiple providers (Stripe, Braintree, Adyen, etc.) with built-in data quality challenges.

## Quick Start

### 1. Start the Streaming Stack

```bash
make docker-up
```

This starts:

- Kafka broker on `localhost:9092`
- Flink JobManager UI on `http://localhost:8081`
- Polaris REST catalog on `http://localhost:8181`
- MinIO console on `http://localhost:9001` (admin/password)
- Trino on `http://localhost:8080`
- Dagster on `http://localhost:3000`

### 2. Initialize Polaris Warehouse

One-time setup to create the Polaris warehouse and permissions:

```bash
make docker-polaris-init
```

### 3. Create Kafka Topics

Create topics for all payment event types:

```bash
make jr-create-topics
```

### 4. Submit Streaming Jobs

Auto-submit all streaming jobs with a single command:

```bash
make flink-submit-jobs
```

**What this does:**
1. Waits for Flink, Kafka, and Polaris to be ready
2. Creates Kafka catalog and source tables for all 4 event types:
   - `payment_charges`
   - `payment_refunds`
   - `payment_disputes`
   - `payment_subscriptions`
3. Creates Polaris catalog and Iceberg sink tables
4. Submits persistent streaming jobs: `JR → Kafka → Flink → Iceberg`
5. Jobs run continuously until cancelled or cluster restarts

**Verify the pipeline:**

```bash
# Check Flink Web UI for running jobs
open http://localhost:8081
```

You should see 1 running job with 4 streaming operations (charges, refunds, disputes, subscriptions).

### 5. Generate Payment Events

Start the JR data generators:

```bash
make docker-jr
```

This starts four event generators:

- **jr-charges**: 2 events/second → `payment_charges` topic
- **jr-refunds**: 1 event/2s → `payment_refunds` topic
- **jr-disputes**: 1 event/5s → `payment_disputes` topic
- **jr-subscriptions**: 1 event/3s → `payment_subscriptions` topic

Monitor the generators:

```bash
# View generator logs
docker logs jr-charges --tail=50 -f

# Check status
docker compose ps | grep jr-

# Stop generators
docker compose --profile generators stop
```

### 6. Query Streaming Data

Attach to Flink SQL client to query data:

```bash
make flink-attach
```

```sql
-- Query accumulating data (run multiple times to see count increase)
SELECT COUNT(*) FROM polaris_catalog.payments_db.payment_charges;
SELECT COUNT(*) FROM polaris_catalog.payments_db.payment_refunds;
SELECT COUNT(*) FROM polaris_catalog.payments_db.payment_disputes;
SELECT COUNT(*) FROM polaris_catalog.payments_db.payment_subscriptions;

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

-- Exit when done
exit;
```

## After Cluster Restart

Streaming jobs don't survive cluster restarts. Simply resubmit them:

```bash
make flink-submit-jobs
```

The Iceberg tables and data persist in Polaris/MinIO, so jobs pick up where they left off.

## Payment Event Types

### 1. Payment Charges

**Topic:** `payment_charges` | **Frequency:** 500ms

Transaction details, payment method info, merchant data, risk scoring.

**Data Quality Issues:** null variations, invalid country codes, mixed case currencies

### 2. Payment Refunds

**Topic:** `payment_refunds` | **Frequency:** 2s

Refund details, reasons, status, support ticket references.

**Data Quality Issues:** Null status fields, inconsistent reason formats

### 3. Payment Disputes

**Topic:** `payment_disputes` | **Frequency:** 5s

Dispute details, reason codes, evidence tracking, status workflow.

**Data Quality Issues:** Missing evidence metadata, null currency fields

### 4. Subscription Events

**Topic:** `payment_subscriptions` | **Frequency:** 3s

Subscription lifecycle, plan info, trial periods, discount tracking.

**Data Quality Issues:** Null trial dates, missing promo codes

## Advanced Queries

### Analytics with Trino

```bash
# Connect to Trino
docker compose exec -it trino trino --server localhost:8080 --catalog iceberg
```

```sql
-- Provider performance
SELECT
    provider,
    status,
    COUNT(*) as transaction_count,
    AVG(amount) as avg_amount,
    SUM(amount) as total_amount
FROM payments_db.payment_charges
GROUP BY provider, status
ORDER BY total_amount DESC;

-- Refund analytics
SELECT
    provider,
    reason,
    COUNT(*) as refund_count,
    SUM(amount) as total_refunded
FROM payments_db.payment_refunds
GROUP BY provider, reason
ORDER BY total_refunded DESC;

-- Dispute patterns
SELECT
    provider,
    status,
    reason,
    COUNT(*) as dispute_count,
    SUM(amount) as total_disputed
FROM payments_db.payment_disputes
GROUP BY provider, status, reason
ORDER BY dispute_count DESC;
```

## Monitoring & Debugging

### View Flink Jobs

Open Flink Web UI: `http://localhost:8081`

- Running Jobs: Should show 1 job with 4 streaming operations
- Task Managers: Resource utilization
- Checkpoints: Job recovery points

### Check Kafka Topics

```bash
# List all topics
docker compose exec kafka-broker \
  kafka-topics.sh --list --bootstrap-server localhost:9092

# Consume messages
docker compose exec kafka-broker \
  kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic payment_charges \
  --from-beginning \
  --max-messages 10
```

### View Iceberg Files in MinIO

1. Open MinIO console: `http://localhost:9001`
2. Login: `admin` / `password`
3. Browse: `warehouse/polariscatalog/payments_db/`

You'll see metadata and Parquet data files for each table.

### Check Polaris Catalog

```bash
# Test catalog API
curl http://localhost:8181/api/catalog/v1/config | jq '.'
```

## Troubleshooting

### Jobs Not Running

**Check Flink Web UI:** `http://localhost:8081`

If no jobs are running:

```bash
# Resubmit jobs
make flink-submit-jobs
```

### Timestamp Deserialization Errors

**Symptom:** Flink job keeps restarting with `JsonParseException`

**Solution:** Delete and recreate topic to clear old messages:

```bash
docker exec kafka-broker /opt/kafka/bin/kafka-topics.sh \
  --delete --topic payment_charges --bootstrap-server localhost:9092

make jr-create-topics
make flink-submit-jobs
```

### No Data Flowing

**Check:**
1. JR generators running: `docker compose ps | grep jr-`
2. Flink job running: `http://localhost:8081`
3. Kafka topics exist: `make jr-create-topics`

**Restart pipeline:**

```bash
docker compose restart
make docker-polaris-init
make jr-create-topics
make flink-submit-jobs
make docker-jr
```

## Real-World Use Case: Butter Payments

This setup is inspired by [Butter Payments' Data Engineering role](https://jobs.lever.co/ButterPayments/4d9ae20b-5a36-4e61-acfe-33881896fbc0), focusing on:

1. **Multi-Provider Ingestion**: Events from Stripe, Braintree, Adyen, etc.
2. **Data Normalization**: Standardizing schemas across providers
3. **Data Quality Validation**: Detecting nulls, invalid codes, malformed data
4. **Transformation Layers**: Cleaning data as far upstream as possible
5. **ML Pipeline Support**: Preparing data for machine learning models

**Practice Challenges:**

- Create DBT models to normalize across providers
- Write data quality tests (Flink/DBT)
- Handle duplicate payment events
- Join payment events with customer/merchant data
- Track subscription status changes (SCD Type 2)

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
    CASE WHEN failure_code IN ('null', 'NULL') THEN NULL
         ELSE failure_code
    END as failure_code,
    created_at
FROM source
```

## Makefile Command Reference

```bash
# Core Workflow
make docker-up              # Start all services
make docker-polaris-init    # Initialize Polaris warehouse (one-time)
make jr-create-topics       # Create Kafka topics (one-time)
make flink-submit-jobs      # Auto-submit streaming jobs
make docker-jr              # Start JR generators

# Monitoring
make docker-status          # Show running containers
make docker-logs            # View all logs
make flink-attach           # Attach to Flink SQL client

# Cleanup
make docker-down            # Stop all services
make docker-restart         # Restart services
```

## References

- [Blog: Streaming Data Lakehouse with Flink and Iceberg](https://blog.det.life/streaming-data-lakehouse-part-2-flink-kafka-and-jr-for-real-time-ingestion-4dcd5dba8bbc)
- [Butter Payments Data Engineering Role](https://jobs.lever.co/ButterPayments/4d9ae20b-5a36-4e61-acfe-33881896fbc0)
- [Apache Flink Iceberg Connector](https://iceberg.apache.org/docs/latest/flink/)
- [JR Data Generator](https://github.com/ugol/jr)
- [Apache Polaris REST Catalog](https://polaris.apache.org/)
