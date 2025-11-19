-- ============================================================================
-- Staging Model: Payment Refunds
-- ============================================================================
-- Purpose: Staging layer for refund events with business validation
-- Source: Bronze payment_refunds table (validated by Flink)
-- Materialization: Incremental (merge strategy for late-arriving data)
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='event_id',
    incremental_strategy='merge',
    file_format='iceberg',
    partition_by=['DATE(created_at)'],
    tags=['staging', 'payments', 'refunds']
  )
}}

WITH source AS (
    SELECT * FROM {{ source('bronze_payments', 'payment_refunds') }}
    {% if is_incremental() %}
    WHERE created_at > (SELECT MAX(created_at) FROM {{ this }})
    {% endif %}
),

business_validated AS (
    SELECT
        -- Identity Fields
        event_id,
        event_type,
        provider,
        refund_id,
        charge_id,
        customer_id,

        -- Financial Fields
        amount,
        currency,

        -- Status & Reason
        status,
        reason,
        failure_reason,

        -- Merchant Details
        merchant_id,

        -- Metadata
        metadata,

        -- Timestamps
        created_at,
        updated_at,

        -- Data Quality Flags
        validation_flag,

        -- Business Validation
        CASE
            WHEN amount IS NULL THEN 'INVALID_AMOUNT'
            WHEN currency IS NULL THEN 'INVALID_CURRENCY'
            WHEN status = 'failed' AND failure_reason IS NULL
                THEN 'MISSING_FAILURE_REASON'
            WHEN amount > 100000.00
                THEN 'SUSPICIOUS_LARGE_REFUND'
            ELSE NULL
        END AS validation_error

    FROM source
)

SELECT
    event_id,
    event_type,
    provider,
    refund_id,
    charge_id,
    customer_id,
    amount,
    currency,
    status,
    reason,
    failure_reason,
    merchant_id,
    metadata,
    created_at,
    updated_at,
    validation_flag
FROM business_validated
WHERE validation_error IS NULL
