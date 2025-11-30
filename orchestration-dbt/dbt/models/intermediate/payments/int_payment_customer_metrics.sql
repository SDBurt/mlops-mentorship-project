-- ============================================================================
-- Intermediate Model: Customer Payment Metrics
-- ============================================================================
-- Purpose: Aggregate customer-level payment metrics for dimensions and ML features
-- Source: Bronze payment_events from Dagster ingestion
-- Materialization: Ephemeral (not persisted, used as building block)
-- ============================================================================

{{
  config(
    materialized='ephemeral',
    tags=['intermediate', 'payments', 'customers']
  )
}}

WITH payment_events AS (
    -- Reference staging model for proper lineage
    SELECT * FROM {{ ref('stg_payment_events') }}
    WHERE customer_id IS NOT NULL
),

-- Aggregate metrics per customer
customer_metrics AS (
    SELECT
        customer_id,

        -- Transaction counts
        COUNT(*) AS total_transactions,
        COUNT(CASE WHEN status = 'succeeded' THEN 1 END) AS successful_transactions,
        COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failed_transactions,
        COUNT(CASE WHEN status = 'refunded' OR event_type LIKE '%refund%' THEN 1 END) AS refunded_transactions,

        -- Revenue metrics (in cents)
        COALESCE(SUM(CASE WHEN status = 'succeeded' THEN amount_cents END), 0) AS total_revenue_cents,
        COALESCE(AVG(CASE WHEN status = 'succeeded' THEN amount_cents END), 0) AS avg_transaction_cents,
        COALESCE(MAX(CASE WHEN status = 'succeeded' THEN amount_cents END), 0) AS max_transaction_cents,
        COALESCE(MIN(CASE WHEN status = 'succeeded' THEN amount_cents END), 0) AS min_transaction_cents,

        -- Failure metrics
        {{ safe_divide(
            'COUNT(CASE WHEN status = \'failed\' THEN 1 END)',
            'COUNT(*)'
        ) }} AS failure_rate,

        -- Fraud metrics (averages of ML scores)
        AVG(fraud_score) AS avg_fraud_score,
        MAX(fraud_score) AS max_fraud_score,
        COUNT(CASE WHEN risk_level = 'high' THEN 1 END) AS high_risk_transaction_count,

        -- Churn metrics
        AVG(churn_score) AS avg_churn_score,
        MAX(churn_score) AS max_churn_score,
        MIN(days_to_churn_estimate) AS min_days_to_churn,

        -- Payment method preferences (using arbitrary to get a representative value)
        arbitrary(payment_method_type) AS preferred_payment_method,
        arbitrary(card_brand) AS preferred_card_brand,
        arbitrary(currency) AS preferred_currency,

        -- Temporal metrics
        MIN(provider_created_at) AS first_transaction_at,
        MAX(provider_created_at) AS last_transaction_at,
        COUNT(DISTINCT DATE(provider_created_at)) AS active_days,

        -- Provider diversity
        COUNT(DISTINCT provider) AS provider_count,
        COUNT(DISTINCT merchant_id) AS merchant_count

    FROM payment_events
    GROUP BY customer_id
)

SELECT
    customer_id,

    -- Transaction metrics
    total_transactions,
    successful_transactions,
    failed_transactions,
    refunded_transactions,

    -- Revenue metrics
    total_revenue_cents,
    {{ cents_to_dollars('total_revenue_cents') }} AS total_revenue_dollars,
    avg_transaction_cents,
    {{ cents_to_dollars('avg_transaction_cents') }} AS avg_transaction_dollars,
    max_transaction_cents,
    min_transaction_cents,

    -- Failure metrics
    failure_rate,
    {{ risk_profile('failure_rate') }} AS payment_risk_profile,

    -- Fraud metrics
    avg_fraud_score,
    max_fraud_score,
    high_risk_transaction_count,
    {{ fraud_risk_level('avg_fraud_score') }} AS fraud_risk_category,

    -- Churn metrics
    avg_churn_score,
    max_churn_score,
    min_days_to_churn,
    {{ churn_risk_level('avg_churn_score') }} AS churn_risk_category,

    -- Payment preferences
    preferred_payment_method,
    preferred_card_brand,
    preferred_currency,

    -- Customer tier (based on total revenue)
    {{ customer_tier('total_revenue_cents') }} AS customer_tier,

    -- Temporal metrics
    first_transaction_at,
    last_transaction_at,
    active_days,
    date_diff('day', first_transaction_at, last_transaction_at) AS customer_tenure_days,

    -- Diversity metrics
    provider_count,
    merchant_count

FROM customer_metrics
