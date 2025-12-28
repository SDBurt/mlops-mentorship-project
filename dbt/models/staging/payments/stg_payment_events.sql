-- ============================================================================
-- Staging Model: Payment Events
-- ============================================================================
-- Purpose: Staging layer for all payment events from PostgreSQL bronze layer
-- Source: Bronze payment_events table (ingested by Dagster from PostgreSQL)
-- Materialization: Incremental (merge strategy for idempotent loads)
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='event_id',
    incremental_strategy='merge',
    tags=['staging', 'payments']
  )
}}

WITH source AS (
    SELECT * FROM {{ source('bronze_payments', 'payment_events') }}
    {% if is_incremental() %}
    WHERE ingested_at > (SELECT MAX(ingested_at) FROM {{ this }})
    {% endif %}
),

cleaned AS (
    SELECT
        -- Identity Fields
        event_id,
        provider,
        provider_event_id,
        event_type,

        -- Entity References
        customer_id,
        merchant_id,

        -- Transaction Details
        amount_cents,
        currency,
        payment_method_type,
        card_brand,
        card_last_four,

        -- Status & Failure Info
        status,
        failure_code,
        failure_message,

        -- ML Enrichment (from Temporal inference)
        fraud_score,
        risk_level,
        retry_strategy,
        retry_delay_seconds,
        churn_score,
        churn_risk_level,
        days_to_churn_estimate,

        -- Validation
        validation_status,
        validation_errors,

        -- Timestamps
        provider_created_at,
        processed_at,
        ingested_at,

        -- Metadata
        metadata,
        schema_version,

        -- Derived: Event Category for downstream analysis
        CASE
            WHEN event_type LIKE '%charge%' OR event_type LIKE '%payment%succeeded%' THEN 'charge'
            WHEN event_type LIKE '%refund%' THEN 'refund'
            WHEN event_type LIKE '%dispute%' THEN 'dispute'
            WHEN event_type LIKE '%subscription%' THEN 'subscription'
            WHEN event_type LIKE '%failed%' THEN 'failed_payment'
            ELSE 'other'
        END AS event_category

    FROM source
    WHERE event_id IS NOT NULL
)

SELECT * FROM cleaned
