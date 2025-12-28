-- ============================================================================
-- Dimension Model: Customer
-- ============================================================================
-- Purpose: Customer dimension with metrics, tier classification, and SCD Type 2
-- Source: Intermediate customer metrics
-- Materialization: Incremental with merge strategy
-- ============================================================================

-- depends_on: {{ ref('stg_payment_events') }}

{{
  config(
    materialized='incremental',
    unique_key='customer_key',
    incremental_strategy='merge',
    format='PARQUET',
    tags=['marts', 'payments', 'dimensions']
  )
}}

WITH customer_metrics AS (
    SELECT * FROM {{ ref('int_payment_customer_metrics') }}
),

-- Generate surrogate key and add SCD columns
dimensioned AS (
    SELECT
        -- Surrogate key
        {{ dbt_utils.generate_surrogate_key(['customer_id']) }} AS customer_key,

        -- Natural key
        customer_id,

        -- Transaction metrics
        total_transactions,
        successful_transactions,
        failed_transactions,
        refunded_transactions,

        -- Revenue metrics
        total_revenue_cents,
        total_revenue_dollars,
        avg_transaction_cents,
        avg_transaction_dollars,
        max_transaction_cents,
        min_transaction_cents,

        -- Payment behavior
        failure_rate,
        payment_risk_profile,
        preferred_payment_method,
        preferred_card_brand,
        preferred_currency,

        -- Tier classification
        customer_tier,

        -- Fraud metrics
        avg_fraud_score,
        max_fraud_score,
        high_risk_transaction_count,
        fraud_risk_category,

        -- Churn metrics
        avg_churn_score,
        max_churn_score,
        min_days_to_churn,
        churn_risk_category,

        -- Temporal metrics
        first_transaction_at,
        last_transaction_at,
        active_days,
        customer_tenure_days,

        -- Diversity metrics
        provider_count,
        merchant_count,

        -- SCD Type 2 columns
        CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS valid_from,
        CAST(NULL AS TIMESTAMP(6) WITH TIME ZONE) AS valid_to,
        TRUE AS is_current,

        -- Audit columns
        CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS dw_created_at,
        CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS dw_updated_at

    FROM customer_metrics
)

SELECT * FROM dimensioned
{% if is_incremental() %}
WHERE customer_id IN (
    -- Reference staging model for proper lineage
    SELECT DISTINCT customer_id
    FROM {{ ref('stg_payment_events') }}
    WHERE ingested_at > (SELECT MAX(dw_updated_at) FROM {{ this }})
)
{% endif %}
