-- Flink Streaming Pipeline - Charges Only
-- Submit only payment_charges streaming job

-- Step 1: Create Kafka catalog
CREATE CATALOG IF NOT EXISTS kafka_catalog WITH ('type'='generic_in_memory');
CREATE DATABASE IF NOT EXISTS kafka_catalog.payments_db;

-- Step 2: Create Polaris catalog
CREATE CATALOG IF NOT EXISTS polaris_catalog WITH (
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

-- Step 4: Create Kafka source table for payment charges
CREATE TABLE IF NOT EXISTS kafka_catalog.payments_db.payment_charges (
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
) WITH (
    'connector' = 'kafka',
    'properties.bootstrap.servers' = 'kafka-broker:29092',
    'properties.group.id' = 'flink-payment-charges-consumer',
    'format' = 'json',
    'json.timestamp-format.standard' = 'SQL',
    'scan.startup.mode' = 'latest-offset',
    'topic' = 'payment_charges'
);

-- Step 5: Create Iceberg sink table for charges
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

-- Step 6: Submit streaming job
INSERT INTO polaris_catalog.payments_db.payment_charges
    SELECT * FROM kafka_catalog.payments_db.payment_charges;
