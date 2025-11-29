-- Step 4: Create Kafka source tables for all payment event types

-- Payment Charges
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
    updated_at TIMESTAMP(3),
    WATERMARK FOR created_at AS created_at - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'properties.bootstrap.servers' = 'kafka-broker:29092',
    'properties.group.id' = 'flink-payment-charges-consumer',
    'format' = 'json',
    'json.timestamp-format.standard' = 'ISO-8601',
    'scan.startup.mode' = 'earliest-offset',
    'topic' = 'payment_charges'
);

-- Payment Refunds
CREATE TABLE IF NOT EXISTS kafka_catalog.payments_db.payment_refunds (
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
    'properties.group.id' = 'flink-payment-refunds-consumer',
    'format' = 'json',
    'json.timestamp-format.standard' = 'ISO-8601',
    'scan.startup.mode' = 'earliest-offset',
    'topic' = 'payment_refunds'
);

-- Payment Disputes
CREATE TABLE IF NOT EXISTS kafka_catalog.payments_db.payment_disputes (
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
    'properties.group.id' = 'flink-payment-disputes-consumer',
    'format' = 'json',
    'json.timestamp-format.standard' = 'ISO-8601',
    'scan.startup.mode' = 'earliest-offset',
    'topic' = 'payment_disputes'
);

-- Payment Subscriptions
CREATE TABLE IF NOT EXISTS kafka_catalog.payments_db.payment_subscriptions (
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
    'properties.group.id' = 'flink-payment-subscriptions-consumer',
    'format' = 'json',
    'json.timestamp-format.standard' = 'ISO-8601',
    'scan.startup.mode' = 'earliest-offset',
    'topic' = 'payment_subscriptions'
);

-- Step 5: Create Iceberg sink tables (schema only, no data yet)

-- Charges Validated table (with validation flag)
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
    updated_at TIMESTAMP(3),
    validation_flag BOOLEAN  -- Flag for suspicious patterns
);

-- Charges Quarantine table (invalid records)
CREATE TABLE IF NOT EXISTS polaris_catalog.payments_db.quarantine_payment_charges (
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
    quarantine_timestamp TIMESTAMP(3),  -- When record was quarantined
    rejection_reason STRING             -- Why it was rejected
);

-- Refunds Validated table
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
    updated_at TIMESTAMP(3),
    validation_flag BOOLEAN
);

-- Refunds Quarantine table
CREATE TABLE IF NOT EXISTS polaris_catalog.payments_db.quarantine_payment_refunds (
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
    quarantine_timestamp TIMESTAMP(3),
    rejection_reason STRING
);

-- Disputes Validated table
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
    updated_at TIMESTAMP(3),
    validation_flag BOOLEAN
);

-- Disputes Quarantine table
CREATE TABLE IF NOT EXISTS polaris_catalog.payments_db.quarantine_payment_disputes (
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
    quarantine_timestamp TIMESTAMP(3),
    rejection_reason STRING
);

-- Subscriptions Validated table
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
    updated_at TIMESTAMP(3),
    validation_flag BOOLEAN
);

-- Subscriptions Quarantine table
CREATE TABLE IF NOT EXISTS polaris_catalog.payments_db.quarantine_payment_subscriptions (
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
    quarantine_timestamp TIMESTAMP(3),
    rejection_reason STRING
);
