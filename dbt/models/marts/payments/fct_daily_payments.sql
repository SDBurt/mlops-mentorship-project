-- ============================================================================
-- Fact Model: Daily Payments
-- ============================================================================
-- Purpose: Daily aggregated payment metrics for dashboards and trending
-- Grain: One row per day
-- Source: Intermediate daily summary
-- Materialization: Incremental with merge strategy
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='date_key',
    incremental_strategy='merge',
    format='PARQUET',
    tags=['marts', 'payments', 'facts', 'daily']
  )
}}

WITH daily_summary AS (
    SELECT * FROM {{ ref('int_payment_daily_summary') }}
    {% if is_incremental() %}
    WHERE event_date > (SELECT MAX(date_key) FROM {{ this }})
    {% endif %}
)

SELECT
    -- Date key (joins to dim_date)
    event_date AS date_key,

    -- Transaction counts
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

    -- Risk metrics
    avg_fraud_score,
    high_risk_count,
    high_risk_rate,

    -- Churn metrics
    avg_churn_score,
    high_churn_risk_count,

    -- Entity metrics
    unique_customers,
    unique_merchants,
    transactions_per_customer,

    -- Provider breakdown
    stripe_transactions,
    square_transactions,
    other_provider_transactions,

    -- Currency breakdown
    usd_transactions,
    eur_transactions,
    gbp_transactions,

    -- Payment method breakdown
    card_transactions,
    bank_transfer_transactions,
    other_method_transactions,

    -- Audit columns
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS dw_created_at,
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS dw_updated_at

FROM daily_summary
