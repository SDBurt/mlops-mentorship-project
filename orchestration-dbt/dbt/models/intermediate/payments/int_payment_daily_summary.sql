-- ============================================================================
-- Intermediate Model: Daily Payment Summary
-- ============================================================================
-- Purpose: Daily aggregations for time-series analytics and dashboards
-- Source: Bronze payment_events from Dagster ingestion
-- Materialization: Ephemeral (not persisted, used as building block)
-- ============================================================================

{{
  config(
    materialized='ephemeral',
    tags=['intermediate', 'payments', 'daily']
  )
}}

WITH payment_events AS (
    SELECT
        *,
        DATE(provider_created_at) AS event_date
    FROM {{ source('bronze_payments', 'payment_events') }}
),

-- Daily aggregations
daily_summary AS (
    SELECT
        event_date,

        -- Transaction counts
        COUNT(*) AS total_transactions,
        COUNT(CASE WHEN status = 'succeeded' THEN 1 END) AS successful_transactions,
        COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failed_transactions,
        COUNT(CASE WHEN event_type LIKE '%refund%' THEN 1 END) AS refund_count,
        COUNT(CASE WHEN event_type LIKE '%dispute%' THEN 1 END) AS dispute_count,

        -- Revenue metrics (in cents)
        COALESCE(SUM(CASE WHEN status = 'succeeded' THEN amount_cents END), 0) AS total_revenue_cents,
        COALESCE(SUM(CASE WHEN event_type LIKE '%refund%' THEN amount_cents END), 0) AS total_refunds_cents,
        COALESCE(AVG(CASE WHEN status = 'succeeded' THEN amount_cents END), 0) AS avg_transaction_cents,

        -- Rate calculations
        {{ safe_divide(
            'COUNT(CASE WHEN status = \'failed\' THEN 1 END)',
            'COUNT(*)'
        ) }} AS failure_rate,
        {{ safe_divide(
            'COUNT(CASE WHEN event_type LIKE \'%refund%\' THEN 1 END)',
            'COUNT(CASE WHEN status = \'succeeded\' THEN 1 END)'
        ) }} AS refund_rate,

        -- Risk metrics
        AVG(fraud_score) AS avg_fraud_score,
        COUNT(CASE WHEN risk_level = 'high' THEN 1 END) AS high_risk_count,

        -- Churn metrics
        AVG(churn_score) AS avg_churn_score,
        COUNT(CASE WHEN churn_risk_level = 'high' THEN 1 END) AS high_churn_risk_count,

        -- Entity counts
        COUNT(DISTINCT customer_id) AS unique_customers,
        COUNT(DISTINCT merchant_id) AS unique_merchants,

        -- Provider breakdown
        COUNT(CASE WHEN provider = 'stripe' THEN 1 END) AS stripe_transactions,
        COUNT(CASE WHEN provider = 'square' THEN 1 END) AS square_transactions,
        COUNT(CASE WHEN provider NOT IN ('stripe', 'square') THEN 1 END) AS other_provider_transactions,

        -- Currency breakdown (top currencies)
        COUNT(CASE WHEN currency = 'USD' THEN 1 END) AS usd_transactions,
        COUNT(CASE WHEN currency = 'EUR' THEN 1 END) AS eur_transactions,
        COUNT(CASE WHEN currency = 'GBP' THEN 1 END) AS gbp_transactions,

        -- Payment method breakdown
        COUNT(CASE WHEN payment_method_type = 'card' THEN 1 END) AS card_transactions,
        COUNT(CASE WHEN payment_method_type = 'bank_transfer' THEN 1 END) AS bank_transfer_transactions,
        COUNT(CASE WHEN payment_method_type NOT IN ('card', 'bank_transfer') THEN 1 END) AS other_method_transactions

    FROM payment_events
    GROUP BY event_date
)

SELECT
    event_date,

    -- Transaction metrics
    total_transactions,
    successful_transactions,
    failed_transactions,
    refund_count,
    dispute_count,

    -- Revenue metrics
    total_revenue_cents,
    {{ cents_to_dollars('total_revenue_cents') }} AS total_revenue_dollars,
    total_refunds_cents,
    {{ cents_to_dollars('total_refunds_cents') }} AS total_refunds_dollars,
    total_revenue_cents - total_refunds_cents AS net_revenue_cents,
    {{ cents_to_dollars('total_revenue_cents - total_refunds_cents') }} AS net_revenue_dollars,
    avg_transaction_cents,
    {{ cents_to_dollars('avg_transaction_cents') }} AS avg_transaction_dollars,

    -- Rate metrics
    failure_rate,
    refund_rate,

    -- Risk metrics
    avg_fraud_score,
    high_risk_count,
    {{ safe_divide('high_risk_count', 'total_transactions') }} AS high_risk_rate,

    -- Churn metrics
    avg_churn_score,
    high_churn_risk_count,

    -- Entity metrics
    unique_customers,
    unique_merchants,
    {{ safe_divide('total_transactions', 'unique_customers') }} AS transactions_per_customer,

    -- Provider breakdown
    stripe_transactions,
    square_transactions,
    other_provider_transactions,

    -- Currency breakdown
    usd_transactions,
    eur_transactions,
    gbp_transactions,

    -- Payment method breakdown
    card_transactions,
    bank_transfer_transactions,
    other_method_transactions

FROM daily_summary
