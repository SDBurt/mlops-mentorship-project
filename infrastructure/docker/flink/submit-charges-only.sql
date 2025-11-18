-- Flink Streaming Pipeline - Charges Only
-- Submit only payment_charges streaming job
--
-- This SQL file uses parameterized placeholders that must be substituted
-- before submission. Use the submit-charges-only.sh wrapper script or
-- ensure the following environment variables are set:
--   - POLARIS_URI: Polaris REST catalog URI (default: http://polaris:8181/api/catalog)
--   - POLARIS_OAUTH_URI: Polaris OAuth2 server URI (default: http://polaris:8181/api/catalog/v1/oauth/tokens)
--   - KAFKA_BOOTSTRAP_SERVERS: Kafka bootstrap servers (default: kafka-broker:29092)
--
-- Example usage:
--   POLARIS_URI=http://polaris:8181/api/catalog \
--   POLARIS_OAUTH_URI=http://polaris:8181/api/catalog/v1/oauth/tokens \
--   KAFKA_BOOTSTRAP_SERVERS=kafka-broker:29092 \
--   bash submit-charges-only.sh

-- Step 1: Create Kafka catalog
CREATE CATALOG IF NOT EXISTS kafka_catalog WITH ('type'='generic_in_memory');
CREATE DATABASE IF NOT EXISTS kafka_catalog.payments_db;

-- Step 2: Create Polaris catalog
CREATE CATALOG IF NOT EXISTS polaris_catalog WITH (
    'type'='iceberg',
    'catalog-type'='rest',
    'uri'='${POLARIS_URI}',
    'warehouse'='polariscatalog',
    'oauth2-server-uri'='${POLARIS_OAUTH_URI}',
    'credential'='root:secret',
    'scope'='PRINCIPAL_ROLE:ALL'
);

CREATE DATABASE IF NOT EXISTS polaris_catalog.payments_db;

-- Step 3: Enable checkpointing (required for Iceberg sinks)
SET 'execution.checkpointing.interval' = '10s';

-- Step 4: Create Kafka source table for payment charges
CREATE TABLE IF NOT EXISTS kafka_catalog.payments_db.payment_charges (
    event_id STRING NOT NULL,
    event_type STRING NOT NULL,
    provider STRING, -- Nullable: payment provider may not be specified for all events
    charge_id STRING NOT NULL,
    customer_id STRING NOT NULL,
    amount DECIMAL(10, 2) NOT NULL, -- Precision: 10 digits total, 2 decimal places for currency
    currency STRING NOT NULL, -- ISO 4217 currency code (e.g., USD, EUR)
    status STRING NOT NULL, -- Payment status: pending, succeeded, failed, refunded
    failure_code STRING, -- Nullable: only present when status='failed'
    failure_message STRING, -- Nullable: only present when status='failed'
    payment_method_id STRING, -- Nullable: may not be available for all payment types
    payment_method_type STRING, -- Nullable: card, bank_transfer, etc.
    card_brand STRING, -- Nullable: only present for card payments
    card_last4 STRING, -- Nullable: only present for card payments
    card_exp_month INT, -- Nullable: only present for card payments (1-12)
    card_exp_year INT, -- Nullable: only present for card payments (4-digit year)
    card_country STRING, -- Nullable: only present for card payments (ISO 3166-1 alpha-2)
    billing_country STRING, -- Nullable: billing address may not be required
    billing_postal_code STRING, -- Nullable: billing address may not be required
    merchant_id STRING, -- Nullable: may not be specified for all events
    merchant_name STRING, -- Nullable: may not be specified for all events
    description STRING, -- Nullable: transaction description may be optional
    metadata ROW<
        order_id STRING, -- Nullable: order reference may not exist
        user_email STRING, -- Nullable: user email may not be available
        subscription_id STRING -- Nullable: only present for subscription-related charges
    >, -- Nullable: metadata is optional
    risk_score INT, -- Nullable: risk assessment may not be available for all transactions
    risk_level STRING, -- Nullable: risk assessment may not be available (low, medium, high)
    `3ds_authenticated` STRING, -- Nullable: 3DS authentication status (true/false/null) - only for card payments
    created_at TIMESTAMP(3) NOT NULL, -- Precision: millisecond precision (3 decimal places)
    updated_at TIMESTAMP(3) -- Nullable: may be null if record never updated (precision: millisecond)
) WITH (
    'connector' = 'kafka',
    'properties.bootstrap.servers' = '${KAFKA_BOOTSTRAP_SERVERS}',
    'properties.group.id' = 'flink-payment-charges-consumer',
    'format' = 'json',
    'json.timestamp-format.standard' = 'SQL',
    'scan.startup.mode' = 'latest-offset',
    'topic' = 'payment_charges'
);

-- Step 5: Create Iceberg sink table for charges
CREATE TABLE IF NOT EXISTS polaris_catalog.payments_db.payment_charges (
    event_id STRING NOT NULL,
    event_type STRING NOT NULL,
    provider STRING, -- Nullable: payment provider may not be specified for all events
    charge_id STRING NOT NULL,
    customer_id STRING NOT NULL,
    amount DECIMAL(10, 2) NOT NULL, -- Precision: 10 digits total, 2 decimal places for currency
    currency STRING NOT NULL, -- ISO 4217 currency code (e.g., USD, EUR)
    status STRING NOT NULL, -- Payment status: pending, succeeded, failed, refunded
    failure_code STRING, -- Nullable: only present when status='failed'
    failure_message STRING, -- Nullable: only present when status='failed'
    payment_method_id STRING, -- Nullable: may not be available for all payment types
    payment_method_type STRING, -- Nullable: card, bank_transfer, etc.
    card_brand STRING, -- Nullable: only present for card payments
    card_last4 STRING, -- Nullable: only present for card payments
    card_exp_month INT, -- Nullable: only present for card payments (1-12)
    card_exp_year INT, -- Nullable: only present for card payments (4-digit year)
    card_country STRING, -- Nullable: only present for card payments (ISO 3166-1 alpha-2)
    billing_country STRING, -- Nullable: billing address may not be required
    billing_postal_code STRING, -- Nullable: billing address may not be required
    merchant_id STRING, -- Nullable: may not be specified for all events
    merchant_name STRING, -- Nullable: may not be specified for all events
    description STRING, -- Nullable: transaction description may be optional
    metadata ROW<
        order_id STRING, -- Nullable: order reference may not exist
        user_email STRING, -- Nullable: user email may not be available
        subscription_id STRING -- Nullable: only present for subscription-related charges
    >, -- Nullable: metadata is optional
    risk_score INT, -- Nullable: risk assessment may not be available for all transactions
    risk_level STRING, -- Nullable: risk assessment may not be available (low, medium, high)
    `3ds_authenticated` STRING, -- Nullable: 3DS authentication status (true/false/null) - only for card payments
    created_at TIMESTAMP(3) NOT NULL, -- Precision: millisecond precision (3 decimal places)
    updated_at TIMESTAMP(3) -- Nullable: may be null if record never updated (precision: millisecond)
);

-- Step 6: Submit streaming job
INSERT INTO polaris_catalog.payments_db.payment_charges
    SELECT * FROM kafka_catalog.payments_db.payment_charges;
