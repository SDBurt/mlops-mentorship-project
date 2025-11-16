#!/bin/bash
# Auto-submit Flink SQL streaming jobs on cluster startup
# This ensures jobs are recreated automatically when cluster restarts

set -e

echo "=================================================="
echo "Flink Streaming Jobs Auto-Submission"
echo "=================================================="
echo ""

# Configuration
FLINK_JOBMANAGER="${FLINK_JOBMANAGER:-flink-jobmanager:8081}"
MAX_WAIT_SECONDS=120
SLEEP_INTERVAL=5

# Wait for Flink JobManager to be ready
echo "Waiting for Flink JobManager to be ready at ${FLINK_JOBMANAGER}..."
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT_SECONDS ]; do
    if curl -s "http://${FLINK_JOBMANAGER}/overview" > /dev/null 2>&1; then
        echo "✓ Flink JobManager is ready"
        break
    fi
    echo "  Waiting... (${ELAPSED}s/${MAX_WAIT_SECONDS}s)"
    sleep $SLEEP_INTERVAL
    ELAPSED=$((ELAPSED + SLEEP_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT_SECONDS ]; then
    echo "❌ Error: Flink JobManager not ready after ${MAX_WAIT_SECONDS}s"
    exit 1
fi

# Wait for Kafka to be ready
echo ""
echo "Waiting for Kafka broker to be ready..."
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT_SECONDS ]; do
    if nc -z kafka-broker 29092 > /dev/null 2>&1; then
        echo "✓ Kafka broker is ready"
        break
    fi
    echo "  Waiting... (${ELAPSED}s/${MAX_WAIT_SECONDS}s)"
    sleep $SLEEP_INTERVAL
    ELAPSED=$((ELAPSED + SLEEP_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT_SECONDS ]; then
    echo "❌ Error: Kafka broker not ready after ${MAX_WAIT_SECONDS}s"
    exit 1
fi

# Wait for Polaris to be ready
echo ""
echo "Waiting for Polaris to be ready..."
ELAPSED=0
POLARIS_READY=false
while [ $ELAPSED -lt $MAX_WAIT_SECONDS ]; do
    if curl -s -u root:secret "http://polaris:8181/api/catalog/v1/config" > /dev/null 2>&1; then
        echo "✓ Polaris is ready"
        POLARIS_READY=true
        break
    fi
    echo "  Waiting... (${ELAPSED}s/${MAX_WAIT_SECONDS}s)"
    sleep $SLEEP_INTERVAL
    ELAPSED=$((ELAPSED + SLEEP_INTERVAL))
done

if [ "$POLARIS_READY" = false ]; then
    echo "⚠️  Warning: Polaris not ready after ${MAX_WAIT_SECONDS}s"
    echo "   Streaming jobs will only use Kafka catalog"
fi

# Check if Polaris warehouse exists
echo ""
echo "Checking Polaris warehouse..."
if [ "$POLARIS_READY" = true ]; then
    if curl -s -u root:secret "http://polaris:8181/api/catalog/v1/warehouse/polariscatalog" > /dev/null 2>&1; then
        echo "✓ Polaris warehouse 'polariscatalog' exists"
        WAREHOUSE_EXISTS=true
    else
        echo "⚠️  Warning: Polaris warehouse 'polariscatalog' not found"
        echo "   Run: cd infrastructure/docker && bash polaris/init-polaris.sh"
        echo "   Skipping Polaris catalog and streaming job creation"
        WAREHOUSE_EXISTS=false
    fi
else
    WAREHOUSE_EXISTS=false
fi

# Submit SQL jobs
echo ""
echo "Submitting Flink SQL jobs..."
echo ""

# Check if jobs are already running
RUNNING_JOBS=$(curl -s "http://${FLINK_JOBMANAGER}/jobs" | grep -o '"status":"RUNNING"' | wc -l || echo "0")
if [ "$RUNNING_JOBS" -gt 0 ]; then
    echo "⚠️  Warning: $RUNNING_JOBS job(s) already running"
    echo "   Skipping job submission to avoid duplicates"
    echo ""
    echo "To recreate jobs, cancel existing jobs first:"
    echo "  1. Open Flink Web UI: http://localhost:8081"
    echo "  2. Cancel running jobs"
    echo "  3. Re-run: make flink-submit-jobs"
    exit 0
fi

# Build complete SQL pipeline
SQL_FILE="/tmp/flink-pipeline-$(date +%s).sql"

cat > "$SQL_FILE" <<'EOF'
-- Flink Streaming Pipeline Auto-Submission
-- This SQL file is auto-generated and submitted on cluster startup

-- Step 1: Create Kafka catalog
CREATE CATALOG kafka_catalog WITH ('type'='generic_in_memory');
CREATE DATABASE kafka_catalog.payments_db;
EOF

# Only add Polaris catalog if warehouse exists
if [ "$WAREHOUSE_EXISTS" = true ]; then
    cat >> "$SQL_FILE" <<'EOF'

-- Step 2: Create Polaris catalog
CREATE CATALOG polaris_catalog WITH (
    'type'='iceberg',
    'catalog-type'='rest',
    'uri'='http://polaris:8181/api/catalog',
    'warehouse'='polariscatalog',
    'oauth2-server-uri'='http://polaris:8181/api/catalog/v1/oauth/tokens',
    'credential'='root:secret',
    'scope'='PRINCIPAL_ROLE:ALL'
);

CREATE DATABASE IF NOT EXISTS polaris_catalog.payments_db;

-- Step 3: Enable checkpointing (required for Iceberg sinks)
SET 'execution.checkpointing.interval' = '10s';
EOF
fi

# Add Kafka source table definitions for all event types
cat >> "$SQL_FILE" <<'EOF'

-- Step 4: Create Kafka source tables for all payment event types

-- Payment Charges
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
    'json.timestamp-format.standard' = 'ISO-8601',
    'scan.startup.mode' = 'latest-offset',
    'topic' = 'payment_charges'
);

-- Payment Refunds
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
    'json.timestamp-format.standard' = 'ISO-8601',
    'scan.startup.mode' = 'latest-offset',
    'topic' = 'payment_refunds'
);

-- Payment Disputes
CREATE TABLE kafka_catalog.payments_db.payment_disputes (
    event_id STRING,
    event_type STRING,
    provider STRING,
    dispute_id STRING,
    charge_id STRING,
    customer_id STRING,
    amount DECIMAL(10, 2),
    currency STRING,
    status STRING,
    reason STRING,
    evidence_due_by TIMESTAMP(3),
    is_charge_refundable STRING,
    merchant_id STRING,
    metadata ROW<
        case_number STRING,
        customer_contacted STRING,
        evidence_submitted STRING
    >,
    network_reason_code STRING,
    created_at TIMESTAMP(3),
    updated_at TIMESTAMP(3),
    WATERMARK FOR created_at AS created_at - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'properties.bootstrap.servers' = 'kafka-broker:29092',
    'format' = 'json',
    'json.timestamp-format.standard' = 'ISO-8601',
    'scan.startup.mode' = 'latest-offset',
    'topic' = 'payment_disputes'
);

-- Payment Subscriptions
CREATE TABLE kafka_catalog.payments_db.payment_subscriptions (
    event_id STRING,
    event_type STRING,
    provider STRING,
    subscription_id STRING,
    customer_id STRING,
    plan_id STRING,
    plan_name STRING,
    amount DECIMAL(10, 2),
    currency STRING,
    `interval` STRING,
    interval_count INT,
    status STRING,
    cancel_at_period_end STRING,
    canceled_at TIMESTAMP(3),
    trial_start TIMESTAMP(3),
    trial_end TIMESTAMP(3),
    current_period_start TIMESTAMP(3),
    current_period_end TIMESTAMP(3),
    payment_method_id STRING,
    merchant_id STRING,
    metadata ROW<
        user_email STRING,
        signup_source STRING,
        promo_code STRING
    >,
    discount ROW<
        coupon_id STRING,
        percent_off INT
    >,
    created_at TIMESTAMP(3),
    updated_at TIMESTAMP(3),
    WATERMARK FOR created_at AS created_at - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'properties.bootstrap.servers' = 'kafka-broker:29092',
    'format' = 'json',
    'json.timestamp-format.standard' = 'ISO-8601',
    'scan.startup.mode' = 'latest-offset',
    'topic' = 'payment_subscriptions'
);
EOF

# Only add Iceberg sinks if Polaris is available
if [ "$WAREHOUSE_EXISTS" = true ]; then
    cat >> "$SQL_FILE" <<'EOF'

-- Step 5: Create Iceberg sink tables (schema only, no data yet)

-- Charges Iceberg table
CREATE TABLE IF NOT EXISTS polaris_catalog.payments_db.payment_charges (
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
    updated_at TIMESTAMP(3)
);

-- Refunds Iceberg table
CREATE TABLE IF NOT EXISTS polaris_catalog.payments_db.payment_refunds (
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
    updated_at TIMESTAMP(3)
);

-- Disputes Iceberg table
CREATE TABLE IF NOT EXISTS polaris_catalog.payments_db.payment_disputes (
    event_id STRING,
    event_type STRING,
    provider STRING,
    dispute_id STRING,
    charge_id STRING,
    customer_id STRING,
    amount DECIMAL(10, 2),
    currency STRING,
    status STRING,
    reason STRING,
    evidence_due_by TIMESTAMP(3),
    is_charge_refundable STRING,
    merchant_id STRING,
    metadata ROW<
        case_number STRING,
        customer_contacted STRING,
        evidence_submitted STRING
    >,
    network_reason_code STRING,
    created_at TIMESTAMP(3),
    updated_at TIMESTAMP(3)
);

-- Subscriptions Iceberg table
CREATE TABLE IF NOT EXISTS polaris_catalog.payments_db.payment_subscriptions (
    event_id STRING,
    event_type STRING,
    provider STRING,
    subscription_id STRING,
    customer_id STRING,
    plan_id STRING,
    plan_name STRING,
    amount DECIMAL(10, 2),
    currency STRING,
    `interval` STRING,
    interval_count INT,
    status STRING,
    cancel_at_period_end STRING,
    canceled_at TIMESTAMP(3),
    trial_start TIMESTAMP(3),
    trial_end TIMESTAMP(3),
    current_period_start TIMESTAMP(3),
    current_period_end TIMESTAMP(3),
    payment_method_id STRING,
    merchant_id STRING,
    metadata ROW<
        user_email STRING,
        signup_source STRING,
        promo_code STRING
    >,
    discount ROW<
        coupon_id STRING,
        percent_off INT
    >,
    created_at TIMESTAMP(3),
    updated_at TIMESTAMP(3)
);

-- Step 6: Submit all streaming jobs as a single statement set
EXECUTE STATEMENT SET
BEGIN
    INSERT INTO polaris_catalog.payments_db.payment_charges
        SELECT * FROM kafka_catalog.payments_db.payment_charges;

    INSERT INTO polaris_catalog.payments_db.payment_refunds
        SELECT * FROM kafka_catalog.payments_db.payment_refunds;

    INSERT INTO polaris_catalog.payments_db.payment_disputes
        SELECT * FROM kafka_catalog.payments_db.payment_disputes;

    INSERT INTO polaris_catalog.payments_db.payment_subscriptions
        SELECT * FROM kafka_catalog.payments_db.payment_subscriptions;
END;
EOF
fi

echo "SQL pipeline file created: $SQL_FILE"
echo ""
echo "Submitting jobs to Flink cluster..."

# Submit SQL file to Flink
if sql-client.sh embedded -f "$SQL_FILE"; then
    echo ""
    echo "✓ Jobs submitted successfully!"
    echo ""

    if [ "$WAREHOUSE_EXISTS" = true ]; then
        echo "Streaming pipeline active:"
        echo "  JR → Kafka → Flink → Iceberg (Polaris + MinIO)"
        echo ""
        echo "Statement set submitted with 4 streaming jobs:"
        echo "  ✓ payment_charges → polaris_catalog.payments_db.payment_charges"
        echo "  ✓ payment_refunds → polaris_catalog.payments_db.payment_refunds"
        echo "  ✓ payment_disputes → polaris_catalog.payments_db.payment_disputes"
        echo "  ✓ payment_subscriptions → polaris_catalog.payments_db.payment_subscriptions"
        echo ""
        echo "Verify:"
        echo "  1. Flink Web UI: http://localhost:8081"
        echo "     Should show 1 job named 'insert-into_default_catalog.default_database.statement_set_...' with 4 subtasks"
        echo "  2. Query data: make flink-attach"
        echo "     SELECT COUNT(*) FROM polaris_catalog.payments_db.payment_charges;"
        echo "     SELECT COUNT(*) FROM polaris_catalog.payments_db.payment_refunds;"
        echo "     SELECT COUNT(*) FROM polaris_catalog.payments_db.payment_disputes;"
        echo "     SELECT COUNT(*) FROM polaris_catalog.payments_db.payment_subscriptions;"
    else
        echo "Kafka catalog created (Polaris catalog skipped - warehouse not initialized)"
        echo ""
        echo "To enable full pipeline:"
        echo "  1. Initialize Polaris: make docker-polaris-init"
        echo "  2. Resubmit jobs: make flink-submit-jobs"
    fi
else
    echo ""
    echo "❌ Error: Job submission failed"
    echo "   Check Flink logs: docker logs flink-jobmanager --tail=50"
    exit 1
fi

# Cleanup
rm -f "$SQL_FILE"

echo ""
echo "=================================================="
echo "Auto-submission complete!"
echo "=================================================="
