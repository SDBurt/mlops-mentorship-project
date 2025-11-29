-- ============================================================================
-- Dimension Model: Merchant
-- ============================================================================
-- Purpose: Merchant dimension with health scoring and metrics
-- Source: Intermediate merchant metrics
-- Materialization: Incremental with merge strategy
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='merchant_key',
    incremental_strategy='merge',
    file_format='iceberg',
    partition_by=['health_category'],
    tags=['marts', 'payments', 'dimensions']
  )
}}

WITH merchant_metrics AS (
    SELECT * FROM {{ ref('int_payment_merchant_metrics') }}
),

-- Generate surrogate key and add SCD columns
dimensioned AS (
    SELECT
        -- Surrogate key
        {{ dbt_utils.generate_surrogate_key(['merchant_id']) }} AS merchant_key,

        -- Natural key
        merchant_id,

        -- Transaction metrics
        total_transactions,
        successful_transactions,
        failed_transactions,
        refund_count,
        dispute_count,

        -- Revenue metrics
        total_revenue_cents,
        total_revenue_dollars,
        total_refunds_cents,
        total_refunds_dollars,
        net_revenue_cents,
        net_revenue_dollars,
        avg_transaction_cents,
        avg_transaction_dollars,

        -- Rate metrics
        failure_rate,
        refund_rate,
        dispute_rate,

        -- Health metrics
        health_score,
        health_category,

        -- Risk metrics
        avg_fraud_score,
        high_risk_transaction_count,
        high_risk_rate,
        fraud_risk_category,

        -- Customer metrics
        unique_customers,
        transactions_per_customer,

        -- Provider and currency
        provider_count,
        primary_provider,
        currency_count,
        primary_currency,

        -- Temporal metrics
        first_transaction_at,
        last_transaction_at,
        active_days,
        merchant_tenure_days,

        -- SCD Type 2 columns
        CURRENT_TIMESTAMP AS valid_from,
        CAST(NULL AS TIMESTAMP) AS valid_to,
        TRUE AS is_current,

        -- Audit columns
        CURRENT_TIMESTAMP AS dw_created_at,
        CURRENT_TIMESTAMP AS dw_updated_at

    FROM merchant_metrics
)

SELECT * FROM dimensioned

{% if is_incremental() %}
-- For incremental runs, only process changed merchants
WHERE merchant_id IN (
    SELECT DISTINCT merchant_id
    FROM {{ source('bronze_payments', 'payment_events') }}
    WHERE ingested_at > (SELECT MAX(dw_updated_at) FROM {{ this }})
)
{% endif %}
