-- ============================================================================
-- Feature Model: Customer Features for ML
-- ============================================================================
-- Purpose: Export customer features for Feast feature store
-- Materialization: Table (persisted for feature store export)
-- Downstream: Feast feature store -> Redis online store
-- ============================================================================

{{
  config(
    materialized='table',
    tags=['features', 'ml', 'customers']
  )
}}

WITH customer_metrics AS (
    SELECT * FROM {{ ref('int_payment_customer_metrics') }}
),

final AS (
    SELECT
        -- Entity key
        customer_id,

        -- Feature timestamp (required by Feast)
        CURRENT_TIMESTAMP AS feature_timestamp,

        -- Payment volume metrics (30d approximated from all-time for now)
        total_transactions AS total_payments_30d,
        total_transactions AS total_payments_90d,
        total_revenue_cents AS total_amount_cents_30d,
        CAST(avg_transaction_cents AS REAL) AS avg_amount_cents,

        -- Failure metrics
        failed_transactions AS failed_payments_30d,
        CAST(failure_rate AS REAL) AS failure_rate_30d,
        failed_transactions AS consecutive_failures,  -- Simplified

        -- Recovery metrics (approximated)
        successful_transactions - failed_transactions AS recovered_payments_30d,
        CAST(1.0 - failure_rate AS REAL) AS recovery_rate_30d,

        -- Engagement signals
        COALESCE(customer_tenure_days, 0) AS days_since_first_payment,
        0 AS days_since_last_payment,  -- Would need current_date comparison
        COALESCE(customer_tenure_days, 0) AS days_since_last_failure,  -- Simplified

        -- Payment method diversity
        provider_count AS payment_method_count,
        CASE WHEN provider_count > 1 THEN 1 ELSE 0 END AS has_backup_payment_method,

        -- Risk indicators
        CAST(COALESCE(avg_fraud_score, 0.0) AS REAL) AS fraud_score_avg,
        COALESCE(high_risk_transaction_count, 0) AS high_risk_payment_count,

        -- Profile features
        customer_tier,
        customer_tenure_days AS subscription_age_days,
        customer_tenure_days AS account_age_days

    FROM customer_metrics
    WHERE customer_id IS NOT NULL
)

SELECT * FROM final
