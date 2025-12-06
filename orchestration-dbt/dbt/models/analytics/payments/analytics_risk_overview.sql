-- ============================================================================
-- Analytics Model: Risk Overview (15-minute intervals)
-- ============================================================================
-- Purpose: Risk and fraud metrics over time for monitoring dashboards
-- Materialization: Incremental (15-minute buckets)
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='interval_key',
    incremental_strategy='merge',
    format='PARQUET',
    tags=['analytics', 'payments', 'risk', 'intervals']
  )
}}

WITH payment_events AS (
    SELECT * FROM {{ ref('stg_payment_events') }}
    {% if is_incremental() %}
    -- Lookback 30 minutes to catch late-arriving events for recent intervals
    WHERE ingested_at > (SELECT MAX(interval_end) - INTERVAL '30' MINUTE FROM {{ this }})
    {% endif %}
),

-- Create 15-minute interval buckets with risk metrics
interval_metrics AS (
    SELECT
        -- Time bucketing
        DATE_TRUNC('hour', ingested_at) +
            INTERVAL '15' MINUTE * FLOOR(EXTRACT(MINUTE FROM ingested_at) / 15) AS interval_start,
        DATE_TRUNC('hour', ingested_at) +
            INTERVAL '15' MINUTE * (FLOOR(EXTRACT(MINUTE FROM ingested_at) / 15) + 1) AS interval_end,
        CAST(ingested_at AS DATE) AS event_date,
        EXTRACT(HOUR FROM ingested_at) AS event_hour,

        -- Transaction counts
        COUNT(*) AS total_transactions,
        COUNT(CASE WHEN status = 'succeeded' THEN 1 END) AS successful_count,
        COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failed_count,

        -- Revenue
        SUM(amount_cents) AS total_amount_cents,
        SUM(CASE WHEN status = 'succeeded' THEN amount_cents ELSE 0 END) AS successful_amount_cents,

        -- Risk category distribution
        COUNT(CASE WHEN risk_level = 'high' THEN 1 END) AS high_risk_count,
        COUNT(CASE WHEN risk_level = 'medium' THEN 1 END) AS medium_risk_count,
        COUNT(CASE WHEN risk_level = 'low' THEN 1 END) AS low_risk_count,

        -- Risk amounts
        SUM(CASE WHEN risk_level = 'high' THEN amount_cents ELSE 0 END) AS high_risk_amount_cents,
        SUM(CASE WHEN risk_level = 'medium' THEN amount_cents ELSE 0 END) AS medium_risk_amount_cents,
        SUM(CASE WHEN risk_level = 'low' THEN amount_cents ELSE 0 END) AS low_risk_amount_cents,

        -- Fraud score stats
        AVG(fraud_score) AS avg_fraud_score,
        MIN(fraud_score) AS min_fraud_score,
        MAX(fraud_score) AS max_fraud_score,

        -- Churn score stats
        AVG(churn_score) AS avg_churn_score,
        MIN(churn_score) AS min_churn_score,
        MAX(churn_score) AS max_churn_score,

        -- Risk by provider
        COUNT(CASE WHEN provider = 'stripe' AND risk_level = 'high' THEN 1 END) AS stripe_high_risk,
        COUNT(CASE WHEN provider = 'square' AND risk_level = 'high' THEN 1 END) AS square_high_risk,
        COUNT(CASE WHEN provider = 'adyen' AND risk_level = 'high' THEN 1 END) AS adyen_high_risk,
        COUNT(CASE WHEN provider = 'braintree' AND risk_level = 'high' THEN 1 END) AS braintree_high_risk,

        -- Risk by payment method
        COUNT(CASE WHEN payment_method_type = 'card' AND risk_level = 'high' THEN 1 END) AS card_high_risk,
        COUNT(CASE WHEN (payment_method_type = 'bank_transfer' OR payment_method_type = 'us_bank_account') AND risk_level = 'high' THEN 1 END) AS bank_high_risk

    FROM payment_events
    WHERE ingested_at IS NOT NULL
    GROUP BY 1, 2, 3, 4
)

SELECT
    -- Unique key for merge
    {{ dbt_utils.generate_surrogate_key(['interval_start']) }} AS interval_key,

    -- Time dimensions
    interval_start,
    interval_end,
    event_date,
    event_hour,
    CONCAT(
        CAST(event_date AS VARCHAR), ' ',
        LPAD(CAST(event_hour AS VARCHAR), 2, '0'), ':',
        LPAD(CAST(EXTRACT(MINUTE FROM interval_start) AS VARCHAR), 2, '0')
    ) AS interval_label,

    -- Transaction metrics
    total_transactions,
    successful_count,
    failed_count,

    -- Amount metrics
    total_amount_cents,
    ROUND(total_amount_cents / 100.0, 2) AS total_amount_dollars,
    successful_amount_cents,
    ROUND(successful_amount_cents / 100.0, 2) AS successful_amount_dollars,

    -- Risk category counts
    high_risk_count,
    medium_risk_count,
    low_risk_count,

    -- Risk category percentages
    ROUND(high_risk_count * 100.0 / NULLIF(total_transactions, 0), 2) AS high_risk_pct,
    ROUND(medium_risk_count * 100.0 / NULLIF(total_transactions, 0), 2) AS medium_risk_pct,
    ROUND(low_risk_count * 100.0 / NULLIF(total_transactions, 0), 2) AS low_risk_pct,

    -- Risk amounts
    high_risk_amount_cents,
    ROUND(high_risk_amount_cents / 100.0, 2) AS high_risk_amount_dollars,
    medium_risk_amount_cents,
    ROUND(medium_risk_amount_cents / 100.0, 2) AS medium_risk_amount_dollars,
    low_risk_amount_cents,
    ROUND(low_risk_amount_cents / 100.0, 2) AS low_risk_amount_dollars,

    -- Fraud score metrics
    ROUND(COALESCE(avg_fraud_score, 0), 4) AS avg_fraud_score,
    ROUND(COALESCE(min_fraud_score, 0), 4) AS min_fraud_score,
    ROUND(COALESCE(max_fraud_score, 0), 4) AS max_fraud_score,

    -- Churn score metrics
    ROUND(COALESCE(avg_churn_score, 0), 4) AS avg_churn_score,
    ROUND(COALESCE(min_churn_score, 0), 4) AS min_churn_score,
    ROUND(COALESCE(max_churn_score, 0), 4) AS max_churn_score,

    -- Provider risk breakdown
    stripe_high_risk,
    square_high_risk,
    adyen_high_risk,
    braintree_high_risk,

    -- Payment method risk breakdown
    card_high_risk,
    bank_high_risk,

    -- Audit
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS dw_updated_at

FROM interval_metrics
ORDER BY interval_start
