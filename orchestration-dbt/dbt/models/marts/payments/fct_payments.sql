-- ============================================================================
-- Fact Model: Payments
-- ============================================================================
-- Purpose: Main payment fact table with dimension foreign keys
-- Grain: One row per payment event
-- Source: Bronze payment_events from Dagster ingestion
-- Materialization: Incremental with merge strategy
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='payment_key',
    incremental_strategy='merge',
    file_format='iceberg',
    partition_by=['DATE(event_date)'],
    tags=['marts', 'payments', 'facts']
  )
}}

WITH payment_events AS (
    SELECT
        *,
        DATE(provider_created_at) AS event_date
    FROM {{ source('bronze_payments', 'payment_events') }}
    {% if is_incremental() %}
    WHERE ingested_at > (SELECT MAX(dw_updated_at) FROM {{ this }})
    {% endif %}
),

-- Join with dimensions to get surrogate keys
fact_payments AS (
    SELECT
        -- Surrogate key for the fact
        {{ dbt_utils.generate_surrogate_key(['pe.event_id']) }} AS payment_key,

        -- Dimension foreign keys
        {{ dbt_utils.generate_surrogate_key(['pe.customer_id']) }} AS customer_key,
        {{ dbt_utils.generate_surrogate_key(['pe.merchant_id']) }} AS merchant_key,
        pe.event_date AS date_key,

        -- Degenerate dimensions (identifiers kept in fact)
        pe.event_id,
        pe.provider,
        pe.provider_event_id,
        pe.event_type,
        {{ event_type_category('pe.event_type') }} AS event_category,

        -- Entity references
        pe.customer_id,
        pe.merchant_id,

        -- Measures - Financial
        pe.amount_cents,
        {{ cents_to_dollars('pe.amount_cents') }} AS amount_dollars,
        pe.currency,

        -- Measures - Status
        pe.status,
        {{ payment_status_category('pe.status') }} AS status_category,
        pe.failure_code,
        pe.failure_message,
        CASE WHEN pe.status = 'succeeded' THEN 1 ELSE 0 END AS is_successful,
        CASE WHEN pe.status = 'failed' THEN 1 ELSE 0 END AS is_failed,
        CASE WHEN pe.event_type LIKE '%refund%' THEN 1 ELSE 0 END AS is_refund,
        CASE WHEN pe.event_type LIKE '%dispute%' THEN 1 ELSE 0 END AS is_dispute,

        -- Measures - Payment Method
        pe.payment_method_type,
        pe.card_brand,
        pe.card_last_four,

        -- Measures - ML Inference
        pe.fraud_score,
        pe.risk_level,
        {{ fraud_risk_level('pe.fraud_score') }} AS fraud_risk_category,
        pe.retry_strategy,
        pe.retry_delay_seconds,
        pe.churn_score,
        pe.churn_risk_level,
        {{ churn_risk_level('pe.churn_score') }} AS churn_risk_category,
        pe.days_to_churn_estimate,

        -- Measures - Validation
        pe.validation_status,
        pe.validation_errors,
        CASE WHEN pe.validation_status = 'passed' THEN 1 ELSE 0 END AS is_valid,

        -- Timestamps
        pe.provider_created_at,
        pe.processed_at,
        pe.ingested_at,
        pe.event_date,

        -- Metadata
        pe.metadata,
        pe.schema_version,

        -- Audit columns
        CURRENT_TIMESTAMP AS dw_created_at,
        CURRENT_TIMESTAMP AS dw_updated_at

    FROM payment_events pe
)

SELECT * FROM fact_payments
