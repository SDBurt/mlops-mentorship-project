-- Create Iceberg tables in Trino for payments_db schema
-- These tables match the Flink SQL definitions in flink/sql/02_tables.sql
-- Tables are created in iceberg.payments_db (maps to Polaris warehouse polariscatalog)

-- Charges Validated table (with validation flag)
CREATE TABLE IF NOT EXISTS iceberg.payments_db.payment_charges (
    event_id VARCHAR,
    event_type VARCHAR,
    provider VARCHAR,
    charge_id VARCHAR,
    customer_id VARCHAR,
    amount DECIMAL(10, 2),
    currency VARCHAR,
    status VARCHAR,
    failure_code VARCHAR,
    failure_message VARCHAR,
    payment_method_id VARCHAR,
    payment_method_type VARCHAR,
    card_brand VARCHAR,
    card_last4 VARCHAR,
    card_exp_month INTEGER,
    card_exp_year INTEGER,
    card_country VARCHAR,
    billing_country VARCHAR,
    billing_postal_code VARCHAR,
    merchant_id VARCHAR,
    merchant_name VARCHAR,
    description VARCHAR,
    metadata ROW(
        order_id VARCHAR,
        user_email VARCHAR,
        subscription_id VARCHAR
    ),
    risk_score INTEGER,
    risk_level VARCHAR,
    "3ds_authenticated" VARCHAR,
    created_at TIMESTAMP(3),
    updated_at TIMESTAMP(3),
    validation_flag BOOLEAN
)
WITH (
    format = 'PARQUET'
);

-- Charges Quarantine table (invalid records)
CREATE TABLE IF NOT EXISTS iceberg.payments_db.quarantine_payment_charges (
    event_id VARCHAR,
    event_type VARCHAR,
    provider VARCHAR,
    charge_id VARCHAR,
    customer_id VARCHAR,
    amount DECIMAL(10, 2),
    currency VARCHAR,
    status VARCHAR,
    failure_code VARCHAR,
    failure_message VARCHAR,
    payment_method_id VARCHAR,
    payment_method_type VARCHAR,
    card_brand VARCHAR,
    card_last4 VARCHAR,
    card_exp_month INTEGER,
    card_exp_year INTEGER,
    card_country VARCHAR,
    billing_country VARCHAR,
    billing_postal_code VARCHAR,
    merchant_id VARCHAR,
    merchant_name VARCHAR,
    description VARCHAR,
    metadata ROW(
        order_id VARCHAR,
        user_email VARCHAR,
        subscription_id VARCHAR
    ),
    risk_score INTEGER,
    risk_level VARCHAR,
    "3ds_authenticated" VARCHAR,
    created_at TIMESTAMP(3),
    updated_at TIMESTAMP(3),
    quarantine_timestamp TIMESTAMP(3),
    rejection_reason VARCHAR
)
WITH (
    format = 'PARQUET'
);

-- Refunds Validated table
CREATE TABLE IF NOT EXISTS iceberg.payments_db.payment_refunds (
    event_id VARCHAR,
    event_type VARCHAR,
    provider VARCHAR,
    refund_id VARCHAR,
    charge_id VARCHAR,
    customer_id VARCHAR,
    amount DECIMAL(10, 2),
    currency VARCHAR,
    status VARCHAR,
    reason VARCHAR,
    failure_reason VARCHAR,
    merchant_id VARCHAR,
    metadata ROW(
        refund_requested_by VARCHAR,
        original_order_id VARCHAR,
        support_ticket_id VARCHAR
    ),
    created_at TIMESTAMP(3),
    updated_at TIMESTAMP(3),
    validation_flag BOOLEAN
)
WITH (
    format = 'PARQUET'
);

-- Refunds Quarantine table
CREATE TABLE IF NOT EXISTS iceberg.payments_db.quarantine_payment_refunds (
    event_id VARCHAR,
    event_type VARCHAR,
    provider VARCHAR,
    refund_id VARCHAR,
    charge_id VARCHAR,
    customer_id VARCHAR,
    amount DECIMAL(10, 2),
    currency VARCHAR,
    status VARCHAR,
    reason VARCHAR,
    failure_reason VARCHAR,
    merchant_id VARCHAR,
    metadata ROW(
        refund_requested_by VARCHAR,
        original_order_id VARCHAR,
        support_ticket_id VARCHAR
    ),
    created_at TIMESTAMP(3),
    updated_at TIMESTAMP(3),
    quarantine_timestamp TIMESTAMP(3),
    rejection_reason VARCHAR
)
WITH (
    format = 'PARQUET'
);

-- Disputes Validated table
CREATE TABLE IF NOT EXISTS iceberg.payments_db.payment_disputes (
    event_id VARCHAR,
    event_type VARCHAR,
    provider VARCHAR,
    dispute_id VARCHAR,
    charge_id VARCHAR,
    customer_id VARCHAR,
    amount DECIMAL(10, 2),
    currency VARCHAR,
    status VARCHAR,
    reason VARCHAR,
    evidence_due_by TIMESTAMP(3),
    is_charge_refundable VARCHAR,
    merchant_id VARCHAR,
    metadata ROW(
        case_number VARCHAR,
        customer_contacted VARCHAR,
        evidence_submitted VARCHAR
    ),
    network_reason_code VARCHAR,
    created_at TIMESTAMP(3),
    updated_at TIMESTAMP(3),
    validation_flag BOOLEAN
)
WITH (
    format = 'PARQUET'
);

-- Disputes Quarantine table
CREATE TABLE IF NOT EXISTS iceberg.payments_db.quarantine_payment_disputes (
    event_id VARCHAR,
    event_type VARCHAR,
    provider VARCHAR,
    dispute_id VARCHAR,
    charge_id VARCHAR,
    customer_id VARCHAR,
    amount DECIMAL(10, 2),
    currency VARCHAR,
    status VARCHAR,
    reason VARCHAR,
    evidence_due_by TIMESTAMP(3),
    is_charge_refundable VARCHAR,
    merchant_id VARCHAR,
    metadata ROW(
        case_number VARCHAR,
        customer_contacted VARCHAR,
        evidence_submitted VARCHAR
    ),
    network_reason_code VARCHAR,
    created_at TIMESTAMP(3),
    updated_at TIMESTAMP(3),
    quarantine_timestamp TIMESTAMP(3),
    rejection_reason VARCHAR
)
WITH (
    format = 'PARQUET'
);

-- Subscriptions Validated table
CREATE TABLE IF NOT EXISTS iceberg.payments_db.payment_subscriptions (
    event_id VARCHAR,
    event_type VARCHAR,
    provider VARCHAR,
    subscription_id VARCHAR,
    customer_id VARCHAR,
    plan_id VARCHAR,
    plan_name VARCHAR,
    amount DECIMAL(10, 2),
    currency VARCHAR,
    "interval" VARCHAR,
    interval_count INTEGER,
    status VARCHAR,
    cancel_at_period_end VARCHAR,
    canceled_at TIMESTAMP(3),
    trial_start TIMESTAMP(3),
    trial_end TIMESTAMP(3),
    current_period_start TIMESTAMP(3),
    current_period_end TIMESTAMP(3),
    payment_method_id VARCHAR,
    merchant_id VARCHAR,
    metadata ROW(
        user_email VARCHAR,
        signup_source VARCHAR,
        promo_code VARCHAR
    ),
    discount ROW(
        coupon_id VARCHAR,
        percent_off INTEGER
    ),
    created_at TIMESTAMP(3),
    updated_at TIMESTAMP(3),
    validation_flag BOOLEAN
)
WITH (
    format = 'PARQUET'
);

-- Subscriptions Quarantine table
CREATE TABLE IF NOT EXISTS iceberg.payments_db.quarantine_payment_subscriptions (
    event_id VARCHAR,
    event_type VARCHAR,
    provider VARCHAR,
    subscription_id VARCHAR,
    customer_id VARCHAR,
    plan_id VARCHAR,
    plan_name VARCHAR,
    amount DECIMAL(10, 2),
    currency VARCHAR,
    "interval" VARCHAR,
    interval_count INTEGER,
    status VARCHAR,
    cancel_at_period_end VARCHAR,
    canceled_at TIMESTAMP(3),
    trial_start TIMESTAMP(3),
    trial_end TIMESTAMP(3),
    current_period_start TIMESTAMP(3),
    current_period_end TIMESTAMP(3),
    payment_method_id VARCHAR,
    merchant_id VARCHAR,
    metadata ROW(
        user_email VARCHAR,
        signup_source VARCHAR,
        promo_code VARCHAR
    ),
    discount ROW(
        coupon_id VARCHAR,
        percent_off INTEGER
    ),
    created_at TIMESTAMP(3),
    updated_at TIMESTAMP(3),
    quarantine_timestamp TIMESTAMP(3),
    rejection_reason VARCHAR
)
WITH (
    format = 'PARQUET'
);
