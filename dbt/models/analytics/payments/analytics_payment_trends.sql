-- ============================================================================
-- Analytics Model: Payment Trends
-- ============================================================================
-- Purpose: Time-series data for trend charts and analysis
-- Materialization: Incremental (appends new data)
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='trend_key',
    incremental_strategy='merge',
    format='PARQUET',
    tags=['analytics', 'payments', 'trends']
  )
}}

WITH payment_facts AS (
    SELECT * FROM {{ ref('fct_payments') }}
    {% if is_incremental() %}
    WHERE event_date > (SELECT MAX(date_key) FROM {{ this }})
    {% endif %}
),

date_dim AS (
    SELECT * FROM {{ ref('dim_date') }}
),

-- Daily aggregations
daily_metrics AS (
    SELECT
        pf.event_date AS date_key,

        -- Transaction counts
        COUNT(*) AS transaction_count,
        SUM(is_successful) AS successful_count,
        SUM(is_failed) AS failed_count,
        SUM(is_refund) AS refund_count,
        SUM(is_dispute) AS dispute_count,

        -- Revenue
        SUM(CASE WHEN is_successful = 1 THEN amount_cents ELSE 0 END) AS revenue_cents,
        SUM(CASE WHEN is_refund = 1 THEN amount_cents ELSE 0 END) AS refund_cents,
        AVG(CASE WHEN is_successful = 1 THEN amount_cents ELSE NULL END) AS avg_transaction_cents,

        -- Rates
        CAST(SUM(is_successful) AS DOUBLE) / NULLIF(COUNT(*), 0) AS success_rate,
        CAST(SUM(is_failed) AS DOUBLE) / NULLIF(COUNT(*), 0) AS failure_rate,

        -- Risk
        AVG(fraud_score) AS avg_fraud_score,
        COUNT(CASE WHEN fraud_risk_category = 'high' THEN 1 END) AS high_risk_count,

        -- Churn
        AVG(churn_score) AS avg_churn_score,

        -- Entities
        COUNT(DISTINCT customer_id) AS unique_customers,
        COUNT(DISTINCT merchant_id) AS unique_merchants,

        -- Payment methods
        COUNT(CASE WHEN payment_method_type = 'card' THEN 1 END) AS card_transactions,
        COUNT(CASE WHEN payment_method_type = 'bank_transfer' THEN 1 END) AS bank_transactions,

        -- Providers
        COUNT(CASE WHEN provider = 'stripe' THEN 1 END) AS stripe_transactions,
        COUNT(CASE WHEN provider = 'square' THEN 1 END) AS square_transactions

    FROM payment_facts pf
    GROUP BY pf.event_date
)

SELECT
    -- Unique key for merge
    {{ dbt_utils.generate_surrogate_key(['dm.date_key']) }} AS trend_key,

    -- Date dimensions
    dm.date_key,
    dm.year,
    dm.quarter,
    dm.month,
    dm.week_of_year,
    dm.day_of_week,
    dm.day_name,
    dm.month_name,
    dm.year_month,
    dm.year_quarter,
    dm.is_weekend,
    dm.is_weekday,

    -- Transaction metrics
    COALESCE(m.transaction_count, 0) AS transaction_count,
    COALESCE(m.successful_count, 0) AS successful_count,
    COALESCE(m.failed_count, 0) AS failed_count,
    COALESCE(m.refund_count, 0) AS refund_count,
    COALESCE(m.dispute_count, 0) AS dispute_count,

    -- Revenue metrics
    COALESCE(m.revenue_cents, 0) AS revenue_cents,
    ROUND(COALESCE(m.revenue_cents, 0) / 100.0, 2) AS revenue_dollars,
    COALESCE(m.refund_cents, 0) AS refund_cents,
    ROUND(COALESCE(m.refund_cents, 0) / 100.0, 2) AS refund_dollars,
    COALESCE(m.revenue_cents, 0) - COALESCE(m.refund_cents, 0) AS net_revenue_cents,
    ROUND((COALESCE(m.revenue_cents, 0) - COALESCE(m.refund_cents, 0)) / 100.0, 2) AS net_revenue_dollars,
    ROUND(COALESCE(m.avg_transaction_cents, 0) / 100.0, 2) AS avg_transaction_dollars,

    -- Rate metrics
    ROUND(COALESCE(m.success_rate, 0) * 100, 2) AS success_rate_pct,
    ROUND(COALESCE(m.failure_rate, 0) * 100, 2) AS failure_rate_pct,

    -- Risk metrics
    ROUND(COALESCE(m.avg_fraud_score, 0), 4) AS avg_fraud_score,
    COALESCE(m.high_risk_count, 0) AS high_risk_count,
    ROUND(COALESCE(m.avg_churn_score, 0), 4) AS avg_churn_score,

    -- Entity metrics
    COALESCE(m.unique_customers, 0) AS unique_customers,
    COALESCE(m.unique_merchants, 0) AS unique_merchants,

    -- Payment method breakdown
    COALESCE(m.card_transactions, 0) AS card_transactions,
    COALESCE(m.bank_transactions, 0) AS bank_transactions,

    -- Provider breakdown
    COALESCE(m.stripe_transactions, 0) AS stripe_transactions,
    COALESCE(m.square_transactions, 0) AS square_transactions,

    -- Running totals (can be used for cumulative charts)
    SUM(COALESCE(m.revenue_cents, 0)) OVER (
        ORDER BY dm.date_key
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_revenue_cents,

    -- 7-day moving averages
    AVG(COALESCE(m.transaction_count, 0)) OVER (
        ORDER BY dm.date_key
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS ma7_transaction_count,

    AVG(COALESCE(m.revenue_cents, 0)) OVER (
        ORDER BY dm.date_key
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS ma7_revenue_cents,

    -- Audit
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS dw_updated_at

FROM date_dim dm
LEFT JOIN daily_metrics m ON dm.date_key = m.date_key
WHERE dm.date_key <= CURRENT_DATE
  AND dm.date_key >= DATE '2024-01-01'
