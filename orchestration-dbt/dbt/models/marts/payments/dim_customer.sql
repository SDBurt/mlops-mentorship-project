-- ============================================================================
-- Dimension Model: Customer
-- ============================================================================
-- Purpose: Customer dimension with metrics, tier classification, and SCD Type 2
-- Source: Intermediate customer metrics
-- Materialization: Incremental with merge strategy
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='customer_key',
    incremental_strategy='merge',
    file_format='iceberg',
    partition_by=['customer_tier'],
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
        CURRENT_TIMESTAMP AS valid_from,
        CAST(NULL AS TIMESTAMP) AS valid_to,
        TRUE AS is_current,

        -- Audit columns
        CURRENT_TIMESTAMP AS dw_created_at,
        CURRENT_TIMESTAMP AS dw_updated_at

    FROM customer_metrics
)

SELECT * FROM dimensioned

{% if is_incremental() %}
-- For incremental runs, only process changed customers
WHERE customer_id IN (
    SELECT DISTINCT customer_id
    FROM {{ source('bronze_payments', 'payment_events') }}
    WHERE ingested_at > (SELECT MAX(dw_updated_at) FROM {{ this }})
)
{% endif %}
