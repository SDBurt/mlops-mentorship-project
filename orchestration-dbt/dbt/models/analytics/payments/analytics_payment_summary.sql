-- ============================================================================
-- Analytics Model: Payment Summary KPIs
-- ============================================================================
-- Purpose: High-level KPIs for executive dashboards
-- Materialization: Table (refreshed on schedule)
-- ============================================================================

{{
  config(
    materialized='table',
    format='PARQUET',
    tags=['analytics', 'payments', 'kpis']
  )
}}

WITH payment_facts AS (
    SELECT * FROM {{ ref('fct_payments') }}
),

daily_facts AS (
    SELECT * FROM {{ ref('fct_daily_payments') }}
),

-- Overall metrics
overall_metrics AS (
    SELECT
        COUNT(*) AS total_transactions,
        SUM(is_successful) AS successful_transactions,
        SUM(is_failed) AS failed_transactions,
        SUM(is_refund) AS refunds,
        SUM(is_dispute) AS disputes,

        SUM(CASE WHEN is_successful = 1 THEN amount_cents ELSE 0 END) AS total_revenue_cents,
        SUM(CASE WHEN is_refund = 1 THEN amount_cents ELSE 0 END) AS total_refunds_cents,

        AVG(CASE WHEN is_successful = 1 THEN amount_cents ELSE NULL END) AS avg_transaction_cents,

        -- Success rate
        CAST(SUM(is_successful) AS DOUBLE) / NULLIF(COUNT(*), 0) * 100 AS success_rate,
        CAST(SUM(is_failed) AS DOUBLE) / NULLIF(COUNT(*), 0) * 100 AS failure_rate,
        CAST(SUM(is_refund) AS DOUBLE) / NULLIF(COUNT(*), 0) * 100 AS refund_rate,

        -- Risk metrics
        AVG(fraud_score) AS avg_fraud_score,
        COUNT(CASE WHEN fraud_risk_category = 'high' THEN 1 END) AS high_risk_transactions,

        -- Customer metrics
        COUNT(DISTINCT customer_id) AS unique_customers,
        COUNT(DISTINCT merchant_id) AS unique_merchants,

        -- Time boundaries
        MIN(event_date) AS first_transaction_date,
        MAX(event_date) AS last_transaction_date

    FROM payment_facts
),

-- Period comparisons (last 7 days vs prior 7 days)
recent_metrics AS (
    SELECT
        SUM(total_transactions) AS last_7d_transactions,
        SUM(total_revenue_cents) AS last_7d_revenue_cents,
        AVG(failure_rate) AS last_7d_failure_rate
    FROM daily_facts
    WHERE date_key >= CURRENT_DATE - INTERVAL '7' DAY
),

prior_metrics AS (
    SELECT
        SUM(total_transactions) AS prior_7d_transactions,
        SUM(total_revenue_cents) AS prior_7d_revenue_cents,
        AVG(failure_rate) AS prior_7d_failure_rate
    FROM daily_facts
    WHERE date_key >= CURRENT_DATE - INTERVAL '14' DAY
      AND date_key < CURRENT_DATE - INTERVAL '7' DAY
)

SELECT
    -- Snapshot timestamp
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS snapshot_at,

    -- Overall KPIs
    o.total_transactions,
    o.successful_transactions,
    o.failed_transactions,
    o.refunds,
    o.disputes,

    o.total_revenue_cents,
    ROUND(o.total_revenue_cents / 100.0, 2) AS total_revenue_dollars,
    o.total_refunds_cents,
    ROUND(o.total_refunds_cents / 100.0, 2) AS total_refunds_dollars,
    o.total_revenue_cents - o.total_refunds_cents AS net_revenue_cents,
    ROUND((o.total_revenue_cents - o.total_refunds_cents) / 100.0, 2) AS net_revenue_dollars,

    o.avg_transaction_cents,
    ROUND(o.avg_transaction_cents / 100.0, 2) AS avg_transaction_dollars,

    -- Rates
    ROUND(o.success_rate, 2) AS success_rate_pct,
    ROUND(o.failure_rate, 2) AS failure_rate_pct,
    ROUND(o.refund_rate, 2) AS refund_rate_pct,

    -- Risk
    ROUND(o.avg_fraud_score, 4) AS avg_fraud_score,
    o.high_risk_transactions,

    -- Entity counts
    o.unique_customers,
    o.unique_merchants,

    -- Time range
    o.first_transaction_date,
    o.last_transaction_date,

    -- Period over period
    r.last_7d_transactions,
    r.last_7d_revenue_cents,
    ROUND(r.last_7d_revenue_cents / 100.0, 2) AS last_7d_revenue_dollars,

    p.prior_7d_transactions,
    p.prior_7d_revenue_cents,
    ROUND(p.prior_7d_revenue_cents / 100.0, 2) AS prior_7d_revenue_dollars,

    -- Growth rates
    CASE
        WHEN p.prior_7d_transactions > 0
        THEN ROUND((r.last_7d_transactions - p.prior_7d_transactions) * 100.0 / p.prior_7d_transactions, 2)
        ELSE NULL
    END AS transaction_growth_pct,

    CASE
        WHEN p.prior_7d_revenue_cents > 0
        THEN ROUND((r.last_7d_revenue_cents - p.prior_7d_revenue_cents) * 100.0 / p.prior_7d_revenue_cents, 2)
        ELSE NULL
    END AS revenue_growth_pct

FROM overall_metrics o
CROSS JOIN recent_metrics r
CROSS JOIN prior_metrics p
