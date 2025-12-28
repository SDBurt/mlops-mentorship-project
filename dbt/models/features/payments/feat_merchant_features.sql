-- ============================================================================
-- Feature Model: Merchant Features for ML
-- ============================================================================
-- Purpose: Export merchant features for Feast feature store
-- Materialization: Table (persisted for feature store export)
-- Downstream: Feast feature store -> Redis online store
-- ============================================================================

{{
  config(
    materialized='table',
    tags=['features', 'ml', 'merchants']
  )
}}

WITH merchant_metrics AS (
    SELECT * FROM {{ ref('int_payment_merchant_metrics') }}
),

final AS (
    SELECT
        -- Entity key
        merchant_id,

        -- Feature timestamp (required by Feast)
        CURRENT_TIMESTAMP AS feature_timestamp,

        -- Volume metrics
        total_transactions AS total_transactions_30d,
        total_revenue_cents AS total_volume_cents_30d,
        unique_customers AS unique_customers_30d,
        CAST(avg_transaction_cents AS REAL) AS avg_transaction_amount,

        -- Quality metrics
        CAST(failure_rate AS REAL) AS failure_rate_30d,
        CAST(dispute_rate AS REAL) AS dispute_rate_30d,
        CAST(refund_rate AS REAL) AS refund_rate_30d,
        CAST(dispute_rate AS REAL) AS chargeback_rate_30d,  -- Using dispute as proxy

        -- Risk metrics
        CAST(COALESCE(avg_fraud_score, 0.0) AS REAL) AS fraud_rate_30d,
        CAST(COALESCE(high_risk_rate, 0.0) AS REAL) AS high_risk_transaction_pct,

        -- Health score
        CAST(health_score AS REAL) AS merchant_health_score

    FROM merchant_metrics
    WHERE merchant_id IS NOT NULL
)

SELECT * FROM final
