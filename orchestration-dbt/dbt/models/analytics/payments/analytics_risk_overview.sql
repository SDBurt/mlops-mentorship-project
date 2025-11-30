-- ============================================================================
-- Analytics Model: Risk Overview
-- ============================================================================
-- Purpose: Risk and fraud metrics for monitoring dashboards
-- Materialization: Table (refreshed frequently)
-- ============================================================================

{{
  config(
    materialized='table',
    format='PARQUET',
    tags=['analytics', 'payments', 'risk']
  )
}}

WITH payment_facts AS (
    SELECT * FROM {{ ref('fct_payments') }}
),

-- Risk score distribution
risk_distribution AS (
    SELECT
        fraud_risk_category,
        COUNT(*) AS transaction_count,
        SUM(amount_cents) AS total_amount_cents,
        AVG(fraud_score) AS avg_fraud_score,
        MIN(fraud_score) AS min_fraud_score,
        MAX(fraud_score) AS max_fraud_score,
        SUM(is_successful) AS successful_count,
        SUM(is_failed) AS failed_count
    FROM payment_facts
    GROUP BY fraud_risk_category
),

-- Risk by provider
risk_by_provider AS (
    SELECT
        provider,
        COUNT(*) AS transaction_count,
        AVG(fraud_score) AS avg_fraud_score,
        COUNT(CASE WHEN fraud_risk_category = 'high' THEN 1 END) AS high_risk_count,
        SUM(CASE WHEN fraud_risk_category = 'high' THEN amount_cents ELSE 0 END) AS high_risk_amount_cents
    FROM payment_facts
    GROUP BY provider
),

-- Risk by payment method
risk_by_method AS (
    SELECT
        payment_method_type,
        COUNT(*) AS transaction_count,
        AVG(fraud_score) AS avg_fraud_score,
        COUNT(CASE WHEN fraud_risk_category = 'high' THEN 1 END) AS high_risk_count
    FROM payment_facts
    WHERE payment_method_type IS NOT NULL
    GROUP BY payment_method_type
),

-- Daily risk trends (last 30 days)
daily_risk AS (
    SELECT
        event_date,
        COUNT(*) AS transaction_count,
        AVG(fraud_score) AS avg_fraud_score,
        COUNT(CASE WHEN fraud_risk_category = 'high' THEN 1 END) AS high_risk_count,
        SUM(CASE WHEN fraud_risk_category = 'high' THEN amount_cents ELSE 0 END) AS high_risk_amount_cents
    FROM payment_facts
    WHERE event_date >= CURRENT_DATE - INTERVAL '30' DAY
    GROUP BY event_date
),

-- Overall stats
overall_stats AS (
    SELECT
        COUNT(*) AS total_transactions,
        SUM(amount_cents) AS total_amount_cents,
        AVG(fraud_score) AS overall_avg_fraud_score,
        COUNT(CASE WHEN fraud_risk_category = 'high' THEN 1 END) AS total_high_risk,
        COUNT(CASE WHEN fraud_risk_category = 'medium' THEN 1 END) AS total_medium_risk,
        COUNT(CASE WHEN fraud_risk_category = 'low' THEN 1 END) AS total_low_risk,
        SUM(CASE WHEN fraud_risk_category = 'high' THEN amount_cents ELSE 0 END) AS high_risk_amount_cents
    FROM payment_facts
)

-- Risk category breakdown
SELECT
    'risk_category' AS metric_type,
    rd.fraud_risk_category AS dimension,
    CAST(NULL AS VARCHAR) AS sub_dimension,
    rd.transaction_count,
    rd.total_amount_cents,
    ROUND(rd.total_amount_cents / 100.0, 2) AS total_amount_dollars,
    ROUND(rd.transaction_count * 100.0 / os.total_transactions, 2) AS transaction_pct,
    ROUND(rd.avg_fraud_score, 4) AS avg_fraud_score,
    rd.successful_count,
    rd.failed_count,
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS snapshot_at
FROM risk_distribution rd
CROSS JOIN overall_stats os

UNION ALL

-- Risk by provider
SELECT
    'provider' AS metric_type,
    rp.provider AS dimension,
    CAST(NULL AS VARCHAR) AS sub_dimension,
    rp.transaction_count,
    NULL AS total_amount_cents,
    NULL AS total_amount_dollars,
    ROUND(rp.high_risk_count * 100.0 / NULLIF(rp.transaction_count, 0), 2) AS transaction_pct,
    ROUND(rp.avg_fraud_score, 4) AS avg_fraud_score,
    NULL AS successful_count,
    rp.high_risk_count AS failed_count,
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS snapshot_at
FROM risk_by_provider rp

UNION ALL

-- Risk by payment method
SELECT
    'payment_method' AS metric_type,
    rm.payment_method_type AS dimension,
    CAST(NULL AS VARCHAR) AS sub_dimension,
    rm.transaction_count,
    NULL AS total_amount_cents,
    NULL AS total_amount_dollars,
    ROUND(rm.high_risk_count * 100.0 / NULLIF(rm.transaction_count, 0), 2) AS transaction_pct,
    ROUND(rm.avg_fraud_score, 4) AS avg_fraud_score,
    NULL AS successful_count,
    rm.high_risk_count AS failed_count,
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS snapshot_at
FROM risk_by_method rm

UNION ALL

-- Overall summary row
SELECT
    'overall' AS metric_type,
    'all' AS dimension,
    CAST(NULL AS VARCHAR) AS sub_dimension,
    os.total_transactions AS transaction_count,
    os.total_amount_cents,
    ROUND(os.total_amount_cents / 100.0, 2) AS total_amount_dollars,
    ROUND(os.total_high_risk * 100.0 / NULLIF(os.total_transactions, 0), 2) AS transaction_pct,
    ROUND(os.overall_avg_fraud_score, 4) AS avg_fraud_score,
    os.total_low_risk AS successful_count,
    os.total_high_risk AS failed_count,
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS snapshot_at
FROM overall_stats os
