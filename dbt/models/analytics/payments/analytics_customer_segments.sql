-- ============================================================================
-- Analytics Model: Customer Segments
-- ============================================================================
-- Purpose: Customer segmentation for targeting and analysis
-- Materialization: Table (refreshed on schedule)
-- ============================================================================

{{
  config(
    materialized='table',
    format='PARQUET',
    tags=['analytics', 'payments', 'customers']
  )
}}

WITH customers AS (
    SELECT * FROM {{ ref('dim_customer') }}
    WHERE is_current = TRUE
),

-- Segment distribution
segment_counts AS (
    SELECT
        customer_tier,
        COUNT(*) AS customer_count,
        SUM(total_revenue_cents) AS segment_revenue_cents,
        AVG(total_revenue_cents) AS avg_revenue_per_customer_cents,
        AVG(total_transactions) AS avg_transactions_per_customer,
        AVG(failure_rate) AS avg_failure_rate,
        AVG(avg_fraud_score) AS avg_fraud_score,
        AVG(avg_churn_score) AS avg_churn_score
    FROM customers
    GROUP BY customer_tier
),

-- Risk segment distribution
risk_counts AS (
    SELECT
        fraud_risk_category,
        COUNT(*) AS customer_count,
        SUM(total_revenue_cents) AS segment_revenue_cents,
        AVG(avg_fraud_score) AS avg_fraud_score
    FROM customers
    GROUP BY fraud_risk_category
),

-- Churn risk distribution
churn_counts AS (
    SELECT
        churn_risk_category,
        COUNT(*) AS customer_count,
        SUM(total_revenue_cents) AS segment_revenue_cents,
        AVG(avg_churn_score) AS avg_churn_score,
        AVG(min_days_to_churn) AS avg_days_to_churn
    FROM customers
    GROUP BY churn_risk_category
),

-- Payment method preferences
payment_method_counts AS (
    SELECT
        preferred_payment_method,
        COUNT(*) AS customer_count,
        SUM(total_revenue_cents) AS segment_revenue_cents
    FROM customers
    WHERE preferred_payment_method IS NOT NULL
    GROUP BY preferred_payment_method
),

-- Overall totals for percentage calculations
totals AS (
    SELECT
        COUNT(*) AS total_customers,
        SUM(total_revenue_cents) AS total_revenue_cents
    FROM customers
)

-- Tier segments
SELECT
    'tier' AS segment_type,
    s.customer_tier AS segment_value,
    s.customer_count,
    ROUND(s.customer_count * 100.0 / t.total_customers, 2) AS customer_pct,
    s.segment_revenue_cents,
    ROUND(s.segment_revenue_cents / 100.0, 2) AS segment_revenue_dollars,
    ROUND(s.segment_revenue_cents * 100.0 / NULLIF(t.total_revenue_cents, 0), 2) AS revenue_pct,
    ROUND(s.avg_revenue_per_customer_cents / 100.0, 2) AS avg_revenue_per_customer_dollars,
    ROUND(s.avg_transactions_per_customer, 1) AS avg_transactions_per_customer,
    ROUND(s.avg_failure_rate * 100, 2) AS avg_failure_rate_pct,
    ROUND(s.avg_fraud_score, 4) AS avg_fraud_score,
    ROUND(s.avg_churn_score, 4) AS avg_churn_score,
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS snapshot_at
FROM segment_counts s
CROSS JOIN totals t

UNION ALL

-- Risk segments
SELECT
    'fraud_risk' AS segment_type,
    r.fraud_risk_category AS segment_value,
    r.customer_count,
    ROUND(r.customer_count * 100.0 / t.total_customers, 2) AS customer_pct,
    r.segment_revenue_cents,
    ROUND(r.segment_revenue_cents / 100.0, 2) AS segment_revenue_dollars,
    ROUND(r.segment_revenue_cents * 100.0 / NULLIF(t.total_revenue_cents, 0), 2) AS revenue_pct,
    NULL AS avg_revenue_per_customer_dollars,
    NULL AS avg_transactions_per_customer,
    NULL AS avg_failure_rate_pct,
    ROUND(r.avg_fraud_score, 4) AS avg_fraud_score,
    NULL AS avg_churn_score,
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS snapshot_at
FROM risk_counts r
CROSS JOIN totals t

UNION ALL

-- Churn segments
SELECT
    'churn_risk' AS segment_type,
    c.churn_risk_category AS segment_value,
    c.customer_count,
    ROUND(c.customer_count * 100.0 / t.total_customers, 2) AS customer_pct,
    c.segment_revenue_cents,
    ROUND(c.segment_revenue_cents / 100.0, 2) AS segment_revenue_dollars,
    ROUND(c.segment_revenue_cents * 100.0 / NULLIF(t.total_revenue_cents, 0), 2) AS revenue_pct,
    NULL AS avg_revenue_per_customer_dollars,
    NULL AS avg_transactions_per_customer,
    NULL AS avg_failure_rate_pct,
    NULL AS avg_fraud_score,
    ROUND(c.avg_churn_score, 4) AS avg_churn_score,
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS snapshot_at
FROM churn_counts c
CROSS JOIN totals t

UNION ALL

-- Payment method segments
SELECT
    'payment_method' AS segment_type,
    p.preferred_payment_method AS segment_value,
    p.customer_count,
    ROUND(p.customer_count * 100.0 / t.total_customers, 2) AS customer_pct,
    p.segment_revenue_cents,
    ROUND(p.segment_revenue_cents / 100.0, 2) AS segment_revenue_dollars,
    ROUND(p.segment_revenue_cents * 100.0 / NULLIF(t.total_revenue_cents, 0), 2) AS revenue_pct,
    NULL AS avg_revenue_per_customer_dollars,
    NULL AS avg_transactions_per_customer,
    NULL AS avg_failure_rate_pct,
    NULL AS avg_fraud_score,
    NULL AS avg_churn_score,
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS snapshot_at
FROM payment_method_counts p
CROSS JOIN totals t
