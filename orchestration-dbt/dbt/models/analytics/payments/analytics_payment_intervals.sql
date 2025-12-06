-- ============================================================================
-- Analytics Model: Payment Intervals (15-minute buckets)
-- ============================================================================
-- Purpose: Time-series data in 15-minute intervals for real-time monitoring
-- Materialization: Incremental (appends new intervals)
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='interval_key',
    incremental_strategy='merge',
    format='PARQUET',
    tags=['analytics', 'payments', 'intervals', 'realtime']
  )
}}

WITH payment_events AS (
    SELECT * FROM {{ ref('stg_payment_events') }}
    {% if is_incremental() %}
    -- Lookback 30 minutes to catch late-arriving events for recent intervals
    WHERE ingested_at > (SELECT MAX(interval_end) - INTERVAL '30' MINUTE FROM {{ this }})
    {% endif %}
),

-- Create 15-minute interval buckets
interval_metrics AS (
    SELECT
        -- Truncate to 15-minute intervals
        DATE_TRUNC('hour', ingested_at) +
            INTERVAL '15' MINUTE * FLOOR(EXTRACT(MINUTE FROM ingested_at) / 15) AS interval_start,

        DATE_TRUNC('hour', ingested_at) +
            INTERVAL '15' MINUTE * (FLOOR(EXTRACT(MINUTE FROM ingested_at) / 15) + 1) AS interval_end,

        -- Date parts for filtering
        CAST(ingested_at AS DATE) AS event_date,
        EXTRACT(HOUR FROM ingested_at) AS event_hour,

        -- Transaction counts by status
        COUNT(*) AS transaction_count,
        COUNT(CASE WHEN status = 'succeeded' THEN 1 END) AS successful_count,
        COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failed_count,
        COUNT(CASE WHEN event_category = 'refund' THEN 1 END) AS refund_count,
        COUNT(CASE WHEN event_category = 'dispute' THEN 1 END) AS dispute_count,

        -- Revenue
        SUM(CASE WHEN status = 'succeeded' THEN amount_cents ELSE 0 END) AS revenue_cents,
        SUM(CASE WHEN event_category = 'refund' THEN amount_cents ELSE 0 END) AS refund_cents,
        AVG(CASE WHEN status = 'succeeded' THEN amount_cents ELSE NULL END) AS avg_transaction_cents,

        -- Rates
        CAST(COUNT(CASE WHEN status = 'succeeded' THEN 1 END) AS DOUBLE) / NULLIF(COUNT(*), 0) AS success_rate,
        CAST(COUNT(CASE WHEN status = 'failed' THEN 1 END) AS DOUBLE) / NULLIF(COUNT(*), 0) AS failure_rate,

        -- Risk metrics
        AVG(fraud_score) AS avg_fraud_score,
        COUNT(CASE WHEN risk_level = 'high' THEN 1 END) AS high_risk_count,
        AVG(churn_score) AS avg_churn_score,

        -- Entity counts
        COUNT(DISTINCT customer_id) AS unique_customers,
        COUNT(DISTINCT merchant_id) AS unique_merchants,

        -- Provider breakdown
        COUNT(CASE WHEN provider = 'stripe' THEN 1 END) AS stripe_count,
        COUNT(CASE WHEN provider = 'square' THEN 1 END) AS square_count,
        COUNT(CASE WHEN provider = 'adyen' THEN 1 END) AS adyen_count,
        COUNT(CASE WHEN provider = 'braintree' THEN 1 END) AS braintree_count,

        -- Payment method breakdown
        COUNT(CASE WHEN payment_method_type = 'card' THEN 1 END) AS card_count,
        COUNT(CASE WHEN payment_method_type = 'bank_transfer' OR payment_method_type = 'us_bank_account' THEN 1 END) AS bank_count

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

    -- Formatted interval for display
    CONCAT(
        CAST(event_date AS VARCHAR), ' ',
        LPAD(CAST(event_hour AS VARCHAR), 2, '0'), ':',
        LPAD(CAST(EXTRACT(MINUTE FROM interval_start) AS VARCHAR), 2, '0')
    ) AS interval_label,

    -- Transaction metrics
    transaction_count,
    successful_count,
    failed_count,
    refund_count,
    dispute_count,

    -- Revenue metrics
    revenue_cents,
    ROUND(revenue_cents / 100.0, 2) AS revenue_dollars,
    refund_cents,
    ROUND(refund_cents / 100.0, 2) AS refund_dollars,
    revenue_cents - refund_cents AS net_revenue_cents,
    ROUND((revenue_cents - refund_cents) / 100.0, 2) AS net_revenue_dollars,
    ROUND(COALESCE(avg_transaction_cents, 0) / 100.0, 2) AS avg_transaction_dollars,

    -- Rate metrics (as percentages)
    ROUND(COALESCE(success_rate, 0) * 100, 2) AS success_rate_pct,
    ROUND(COALESCE(failure_rate, 0) * 100, 2) AS failure_rate_pct,

    -- Risk metrics
    ROUND(COALESCE(avg_fraud_score, 0), 4) AS avg_fraud_score,
    high_risk_count,
    ROUND(COALESCE(avg_churn_score, 0), 4) AS avg_churn_score,

    -- Entity metrics
    unique_customers,
    unique_merchants,

    -- Provider breakdown
    stripe_count,
    square_count,
    adyen_count,
    braintree_count,

    -- Payment method breakdown
    card_count,
    bank_count,

    -- Throughput (transactions per minute in this interval)
    ROUND(transaction_count / 15.0, 2) AS transactions_per_minute,

    -- Audit
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS dw_updated_at

FROM interval_metrics
ORDER BY interval_start
