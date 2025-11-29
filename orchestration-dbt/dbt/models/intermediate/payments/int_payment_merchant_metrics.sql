-- ============================================================================
-- Intermediate Model: Merchant Payment Metrics
-- ============================================================================
-- Purpose: Aggregate merchant-level payment metrics for dimensions and analytics
-- Source: Bronze payment_events from Dagster ingestion
-- Materialization: Ephemeral (not persisted, used as building block)
-- ============================================================================

{{
  config(
    materialized='ephemeral',
    tags=['intermediate', 'payments', 'merchants']
  )
}}

WITH payment_events AS (
    SELECT * FROM {{ source('bronze_payments', 'payment_events') }}
    WHERE merchant_id IS NOT NULL
),

-- Aggregate metrics per merchant
merchant_metrics AS (
    SELECT
        merchant_id,

        -- Transaction counts
        COUNT(*) AS total_transactions,
        COUNT(CASE WHEN status = 'succeeded' THEN 1 END) AS successful_transactions,
        COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failed_transactions,
        COUNT(CASE WHEN event_type LIKE '%refund%' THEN 1 END) AS refund_count,
        COUNT(CASE WHEN event_type LIKE '%dispute%' OR event_type LIKE '%chargeback%' THEN 1 END) AS dispute_count,

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
        {{ safe_divide(
            'COUNT(CASE WHEN event_type LIKE \'%dispute%\' OR event_type LIKE \'%chargeback%\' THEN 1 END)',
            'COUNT(CASE WHEN status = \'succeeded\' THEN 1 END)'
        ) }} AS dispute_rate,

        -- Risk metrics
        AVG(fraud_score) AS avg_fraud_score,
        COUNT(CASE WHEN risk_level = 'high' THEN 1 END) AS high_risk_transaction_count,
        {{ safe_divide(
            'COUNT(CASE WHEN risk_level = \'high\' THEN 1 END)',
            'COUNT(*)'
        ) }} AS high_risk_rate,

        -- Customer metrics
        COUNT(DISTINCT customer_id) AS unique_customers,
        {{ safe_divide('COUNT(*)', 'COUNT(DISTINCT customer_id)') }} AS transactions_per_customer,

        -- Provider diversity
        COUNT(DISTINCT provider) AS provider_count,
        MODE() WITHIN GROUP (ORDER BY provider) AS primary_provider,

        -- Currency distribution
        COUNT(DISTINCT currency) AS currency_count,
        MODE() WITHIN GROUP (ORDER BY currency) AS primary_currency,

        -- Temporal metrics
        MIN(provider_created_at) AS first_transaction_at,
        MAX(provider_created_at) AS last_transaction_at,
        COUNT(DISTINCT DATE(provider_created_at)) AS active_days

    FROM payment_events
    GROUP BY merchant_id
)

SELECT
    merchant_id,

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
    avg_transaction_cents,
    {{ cents_to_dollars('avg_transaction_cents') }} AS avg_transaction_dollars,
    total_revenue_cents - total_refunds_cents AS net_revenue_cents,
    {{ cents_to_dollars('total_revenue_cents - total_refunds_cents') }} AS net_revenue_dollars,

    -- Rate metrics
    failure_rate,
    refund_rate,
    dispute_rate,

    -- Health score calculation
    {{ merchant_health_score('dispute_rate', 'refund_rate', 'failure_rate') }} AS health_score,
    {{ merchant_health_category(
        merchant_health_score('dispute_rate', 'refund_rate', 'failure_rate')
    ) }} AS health_category,

    -- Risk metrics
    avg_fraud_score,
    high_risk_transaction_count,
    high_risk_rate,
    {{ fraud_risk_level('avg_fraud_score') }} AS fraud_risk_category,

    -- Customer metrics
    unique_customers,
    transactions_per_customer,

    -- Provider and currency
    provider_count,
    primary_provider,
    currency_count,
    primary_currency,

    -- Temporal metrics
    first_transaction_at,
    last_transaction_at,
    active_days,
    DATE_DIFF('day', first_transaction_at, last_transaction_at) AS merchant_tenure_days

FROM merchant_metrics
