-- ============================================================================
-- Staging Model: Payment Charges
-- ============================================================================
-- Purpose: Staging layer for payment charge events with business validation
-- Source: Bronze payment_charges table (validated by Flink)
-- Materialization: Incremental (merge strategy for late-arriving data)
-- Upstream Validation: Layer 1 (Flink) + Layer 2 (DBT business rules)
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='event_id',
    incremental_strategy='merge',
    file_format='iceberg',
    partition_by=['DATE(created_at)'],
    tags=['staging', 'payments', 'charges']
  )
}}

WITH source AS (
    SELECT * FROM {{ source('bronze_payments', 'payment_charges') }}
    {% if is_incremental() %}
    -- Only process new records since last run
    WHERE created_at > (SELECT MAX(created_at) FROM {{ this }})
    {% endif %}
),

business_validated AS (
    SELECT
        -- ====================================================================
        -- Identity Fields
        -- ====================================================================
        event_id,
        event_type,
        provider,
        charge_id,
        customer_id,

        -- ====================================================================
        -- Financial Fields (already validated by Flink)
        -- ====================================================================
        amount,
        currency,

        -- ====================================================================
        -- Status & Failure Information
        -- ====================================================================
        status,
        failure_code,
        failure_message,

        -- ====================================================================
        -- Payment Method Details
        -- ====================================================================
        payment_method_id,
        payment_method_type,
        card_brand,
        card_last4,
        card_exp_month,
        card_exp_year,
        card_country,

        -- ====================================================================
        -- Billing Information
        -- ====================================================================
        billing_country,
        billing_postal_code,

        -- ====================================================================
        -- Merchant Details
        -- ====================================================================
        merchant_id,
        merchant_name,
        description,

        -- ====================================================================
        -- Metadata (nested struct)
        -- ====================================================================
        metadata,

        -- ====================================================================
        -- Risk & Security
        -- ====================================================================
        risk_score,
        risk_level,
        `3ds_authenticated`,

        -- ====================================================================
        -- Timestamps
        -- ====================================================================
        created_at,
        updated_at,

        -- ====================================================================
        -- Data Quality Flags
        -- ====================================================================
        validation_flag,

        -- ====================================================================
        -- Business Validation Errors
        -- ====================================================================
        CASE
            WHEN amount IS NULL THEN 'INVALID_AMOUNT'
            WHEN currency IS NULL THEN 'INVALID_CURRENCY'
            WHEN status = 'failed' AND failure_code IS NULL
                THEN 'MISSING_FAILURE_CODE'
            WHEN amount > 100000.00 AND status = 'succeeded'
                THEN 'SUSPICIOUS_LARGE_AMOUNT'
            WHEN status = 'succeeded' AND amount = 0
                THEN 'SUSPICIOUS_ZERO_AMOUNT'
            ELSE NULL
        END AS validation_error

    FROM source
)

-- Only select valid records (no validation errors)
SELECT
    event_id,
    event_type,
    provider,
    charge_id,
    customer_id,
    amount,
    currency,
    status,
    failure_code,
    failure_message,
    payment_method_id,
    payment_method_type,
    card_brand,
    card_last4,
    card_exp_month,
    card_exp_year,
    card_country,
    billing_country,
    billing_postal_code,
    merchant_id,
    merchant_name,
    description,
    metadata,
    risk_score,
    risk_level,
    `3ds_authenticated`,
    created_at,
    updated_at,
    validation_flag
FROM business_validated
WHERE validation_error IS NULL  -- Only allow clean records to Silver layer
