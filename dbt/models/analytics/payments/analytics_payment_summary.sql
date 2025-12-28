-- ============================================================================
-- Analytics Model: Payment Summary KPIs (15-minute intervals)
-- ============================================================================
-- Purpose: High-level KPIs over time for dashboards
-- Materialization: Incremental (15-minute buckets)
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='interval_key',
    incremental_strategy='merge',
    format='PARQUET',
    tags=['analytics', 'payments', 'kpis', 'intervals']
  )
}}

WITH payment_events AS (
    SELECT * FROM {{ ref('stg_payment_events') }}
    {% if is_incremental() %}
    -- Lookback 30 minutes to catch late-arriving events for recent intervals
    WHERE ingested_at > (SELECT MAX(interval_end) - INTERVAL '30' MINUTE FROM {{ this }})
    {% endif %}
),

-- Create 15-minute interval buckets with KPIs
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
        COUNT(CASE WHEN status = 'succeeded' THEN 1 END) AS successful_transactions,
        COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failed_transactions,
        COUNT(CASE WHEN event_category = 'refund' THEN 1 END) AS refunds,
        COUNT(CASE WHEN event_category = 'dispute' THEN 1 END) AS disputes,

        -- Revenue metrics
        SUM(CASE WHEN status = 'succeeded' THEN amount_cents ELSE 0 END) AS total_revenue_cents,
        SUM(CASE WHEN event_category = 'refund' THEN amount_cents ELSE 0 END) AS total_refunds_cents,
        AVG(CASE WHEN status = 'succeeded' THEN amount_cents ELSE NULL END) AS avg_transaction_cents,

        -- Rate calculations
        CAST(COUNT(CASE WHEN status = 'succeeded' THEN 1 END) AS DOUBLE) / NULLIF(COUNT(*), 0) AS success_rate,
        CAST(COUNT(CASE WHEN status = 'failed' THEN 1 END) AS DOUBLE) / NULLIF(COUNT(*), 0) AS failure_rate,
        CAST(COUNT(CASE WHEN event_category = 'refund' THEN 1 END) AS DOUBLE) / NULLIF(COUNT(*), 0) AS refund_rate,

        -- Risk metrics
        AVG(fraud_score) AS avg_fraud_score,
        COUNT(CASE WHEN risk_level = 'high' THEN 1 END) AS high_risk_transactions,

        -- Entity metrics
        COUNT(DISTINCT customer_id) AS unique_customers,
        COUNT(DISTINCT merchant_id) AS unique_merchants,

        -- Provider counts
        COUNT(CASE WHEN provider = 'stripe' THEN 1 END) AS stripe_transactions,
        COUNT(CASE WHEN provider = 'square' THEN 1 END) AS square_transactions,
        COUNT(CASE WHEN provider = 'adyen' THEN 1 END) AS adyen_transactions,
        COUNT(CASE WHEN provider = 'braintree' THEN 1 END) AS braintree_transactions

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

    -- Transaction KPIs
    total_transactions,
    successful_transactions,
    failed_transactions,
    refunds,
    disputes,

    -- Revenue KPIs
    total_revenue_cents,
    ROUND(total_revenue_cents / 100.0, 2) AS total_revenue_dollars,
    total_refunds_cents,
    ROUND(total_refunds_cents / 100.0, 2) AS total_refunds_dollars,
    total_revenue_cents - total_refunds_cents AS net_revenue_cents,
    ROUND((total_revenue_cents - total_refunds_cents) / 100.0, 2) AS net_revenue_dollars,

    -- Average transaction
    ROUND(COALESCE(avg_transaction_cents, 0) / 100.0, 2) AS avg_transaction_dollars,

    -- Rate KPIs (as percentages)
    ROUND(COALESCE(success_rate, 0) * 100, 2) AS success_rate_pct,
    ROUND(COALESCE(failure_rate, 0) * 100, 2) AS failure_rate_pct,
    ROUND(COALESCE(refund_rate, 0) * 100, 2) AS refund_rate_pct,

    -- Risk KPIs
    ROUND(COALESCE(avg_fraud_score, 0), 4) AS avg_fraud_score,
    high_risk_transactions,

    -- Entity KPIs
    unique_customers,
    unique_merchants,

    -- Provider distribution
    stripe_transactions,
    square_transactions,
    adyen_transactions,
    braintree_transactions,

    -- Throughput
    ROUND(total_transactions / 15.0, 2) AS transactions_per_minute,

    -- Audit
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS dw_updated_at

FROM interval_metrics
ORDER BY interval_start
