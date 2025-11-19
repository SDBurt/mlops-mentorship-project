-- ============================================================================
-- Staging Model: Payment Subscriptions
-- ============================================================================
-- Purpose: Staging layer for subscription events with business validation
-- Source: Bronze payment_subscriptions table (validated by Flink)
-- Materialization: Incremental (merge strategy for late-arriving data)
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='event_id',
    incremental_strategy='merge',
    file_format='iceberg',
    partition_by=['DATE(created_at)'],
    tags=['staging', 'payments', 'subscriptions']
  )
}}

WITH source AS (
    SELECT * FROM {{ source('bronze_payments', 'payment_subscriptions') }}
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
        subscription_id,
        customer_id,

        -- Plan Details
        plan_id,
        plan_name,
        amount,
        currency,
        `interval`,
        interval_count,

        -- Subscription Status
        status,
        cancel_at_period_end,
        canceled_at,

        -- Trial Information
        trial_start,
        trial_end,

        -- Billing Period
        current_period_start,
        current_period_end,

        -- Payment Method
        payment_method_id,

        -- Merchant Details
        merchant_id,

        -- Metadata & Discounts
        metadata,
        discount,

        -- Timestamps
        created_at,
        updated_at,

        -- Data Quality Flags
        validation_flag,

        -- Business Validation
        CASE
            WHEN currency IS NULL THEN 'INVALID_CURRENCY'
            WHEN plan_id IS NULL THEN 'MISSING_PLAN_ID'
            WHEN `interval` IS NULL THEN 'MISSING_INTERVAL'
            WHEN amount IS NOT NULL AND amount > 100000.00
                THEN 'SUSPICIOUS_LARGE_SUBSCRIPTION'
            WHEN amount IS NOT NULL AND amount < 0
                THEN 'INVALID_NEGATIVE_AMOUNT'
            ELSE NULL
        END AS validation_error

    FROM source
)

SELECT
    event_id,
    event_type,
    provider,
    subscription_id,
    customer_id,
    plan_id,
    plan_name,
    amount,
    currency,
    `interval`,
    interval_count,
    status,
    cancel_at_period_end,
    canceled_at,
    trial_start,
    trial_end,
    current_period_start,
    current_period_end,
    payment_method_id,
    merchant_id,
    metadata,
    discount,
    created_at,
    updated_at,
    validation_flag
FROM business_validated
WHERE validation_error IS NULL
