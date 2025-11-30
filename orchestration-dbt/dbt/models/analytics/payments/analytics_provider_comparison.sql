-- ============================================================================
-- Analytics Model: Provider Comparison
-- ============================================================================
-- Purpose: Compare payment provider performance for strategic decisions
-- Materialization: Table (refreshed on schedule)
-- ============================================================================

{{
  config(
    materialized='table',
    format='PARQUET',
    tags=['analytics', 'payments', 'providers']
  )
}}

WITH payment_facts AS (
    SELECT * FROM {{ ref('fct_payments') }}
),

provider_metrics AS (
    SELECT
        provider,

        -- Volume metrics
        COUNT(*) AS total_transactions,
        SUM(is_successful) AS successful_transactions,
        SUM(is_failed) AS failed_transactions,
        SUM(is_refund) AS refund_transactions,
        SUM(is_dispute) AS dispute_transactions,

        -- Revenue metrics
        SUM(CASE WHEN is_successful = 1 THEN amount_cents ELSE 0 END) AS total_revenue_cents,
        SUM(CASE WHEN is_refund = 1 THEN amount_cents ELSE 0 END) AS total_refund_cents,
        AVG(CASE WHEN is_successful = 1 THEN amount_cents ELSE NULL END) AS avg_transaction_cents,
        MIN(CASE WHEN is_successful = 1 THEN amount_cents ELSE NULL END) AS min_transaction_cents,
        MAX(CASE WHEN is_successful = 1 THEN amount_cents ELSE NULL END) AS max_transaction_cents,

        -- Rate metrics
        CAST(SUM(is_successful) AS DOUBLE) / NULLIF(COUNT(*), 0) AS success_rate,
        CAST(SUM(is_failed) AS DOUBLE) / NULLIF(COUNT(*), 0) AS failure_rate,
        CAST(SUM(is_refund) AS DOUBLE) / NULLIF(COUNT(*), 0) AS refund_rate,
        CAST(SUM(is_dispute) AS DOUBLE) / NULLIF(COUNT(*), 0) AS dispute_rate,

        -- Risk metrics
        AVG(fraud_score) AS avg_fraud_score,
        COUNT(CASE WHEN fraud_risk_category = 'high' THEN 1 END) AS high_risk_transactions,

        -- Customer diversity
        COUNT(DISTINCT customer_id) AS unique_customers,

        -- Time metrics
        MIN(event_date) AS first_transaction_date,
        MAX(event_date) AS last_transaction_date,
        COUNT(DISTINCT event_date) AS active_days

    FROM payment_facts
    GROUP BY provider
),

totals AS (
    SELECT
        SUM(total_transactions) AS all_transactions,
        SUM(total_revenue_cents) AS all_revenue_cents
    FROM provider_metrics
)

SELECT
    p.provider,

    -- Volume metrics
    p.total_transactions,
    ROUND(p.total_transactions * 100.0 / t.all_transactions, 2) AS transaction_share_pct,
    p.successful_transactions,
    p.failed_transactions,
    p.refund_transactions,
    p.dispute_transactions,

    -- Revenue metrics
    p.total_revenue_cents,
    ROUND(p.total_revenue_cents / 100.0, 2) AS total_revenue_dollars,
    ROUND(p.total_revenue_cents * 100.0 / NULLIF(t.all_revenue_cents, 0), 2) AS revenue_share_pct,
    p.total_refund_cents,
    ROUND(p.total_refund_cents / 100.0, 2) AS total_refund_dollars,
    p.total_revenue_cents - p.total_refund_cents AS net_revenue_cents,
    ROUND((p.total_revenue_cents - p.total_refund_cents) / 100.0, 2) AS net_revenue_dollars,

    -- Average transaction
    ROUND(p.avg_transaction_cents / 100.0, 2) AS avg_transaction_dollars,
    ROUND(p.min_transaction_cents / 100.0, 2) AS min_transaction_dollars,
    ROUND(p.max_transaction_cents / 100.0, 2) AS max_transaction_dollars,

    -- Rate metrics (as percentages)
    ROUND(p.success_rate * 100, 2) AS success_rate_pct,
    ROUND(p.failure_rate * 100, 2) AS failure_rate_pct,
    ROUND(p.refund_rate * 100, 2) AS refund_rate_pct,
    ROUND(p.dispute_rate * 100, 2) AS dispute_rate_pct,

    -- Risk metrics
    ROUND(p.avg_fraud_score, 4) AS avg_fraud_score,
    p.high_risk_transactions,
    ROUND(p.high_risk_transactions * 100.0 / NULLIF(p.total_transactions, 0), 2) AS high_risk_rate_pct,

    -- Customer metrics
    p.unique_customers,
    ROUND(p.total_transactions * 1.0 / NULLIF(p.unique_customers, 0), 2) AS transactions_per_customer,
    ROUND(p.total_revenue_cents / 100.0 / NULLIF(p.unique_customers, 0), 2) AS revenue_per_customer_dollars,

    -- Activity metrics
    p.first_transaction_date,
    p.last_transaction_date,
    p.active_days,
    ROUND(p.total_transactions * 1.0 / NULLIF(p.active_days, 0), 2) AS transactions_per_day,

    -- Audit
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS snapshot_at

FROM provider_metrics p
CROSS JOIN totals t
ORDER BY p.total_transactions DESC
