-- ============================================================================
-- Payment Pipeline Macros
-- ============================================================================
-- Reusable macros for payment data transformations
-- Used across intermediate and mart models
-- ============================================================================


-- ============================================================================
-- Customer Tier Classification
-- ============================================================================
-- Classifies customers into tiers based on total revenue (in cents)
-- Thresholds:
--   Platinum: >= $1000 (100,000 cents)
--   Gold:     >= $500  (50,000 cents)
--   Silver:   >= $100  (10,000 cents)
--   Bronze:   < $100

{% macro customer_tier(total_revenue_cents) %}
  CASE
    WHEN {{ total_revenue_cents }} >= 100000 THEN 'platinum'
    WHEN {{ total_revenue_cents }} >= 50000 THEN 'gold'
    WHEN {{ total_revenue_cents }} >= 10000 THEN 'silver'
    ELSE 'bronze'
  END
{% endmacro %}


-- ============================================================================
-- Risk Profile Classification
-- ============================================================================
-- Classifies risk based on failure rate
-- Thresholds:
--   High:   >= 15% failure rate
--   Medium: >= 5% failure rate
--   Low:    < 5% failure rate

{% macro risk_profile(failure_rate) %}
  CASE
    WHEN {{ failure_rate }} >= 0.15 THEN 'high_risk'
    WHEN {{ failure_rate }} >= 0.05 THEN 'medium_risk'
    ELSE 'low_risk'
  END
{% endmacro %}


-- ============================================================================
-- Fraud Risk Level
-- ============================================================================
-- Classifies fraud risk based on fraud score (0-1)
-- Thresholds:
--   High:   >= 0.7
--   Medium: >= 0.3
--   Low:    < 0.3

{% macro fraud_risk_level(fraud_score) %}
  CASE
    WHEN {{ fraud_score }} >= 0.7 THEN 'high'
    WHEN {{ fraud_score }} >= 0.3 THEN 'medium'
    ELSE 'low'
  END
{% endmacro %}


-- ============================================================================
-- Churn Risk Level
-- ============================================================================
-- Classifies churn risk based on churn score (0-1)
-- Thresholds:
--   High:   >= 0.6
--   Medium: >= 0.3
--   Low:    < 0.3

{% macro churn_risk_level(churn_score) %}
  CASE
    WHEN {{ churn_score }} >= 0.6 THEN 'high'
    WHEN {{ churn_score }} >= 0.3 THEN 'medium'
    ELSE 'low'
  END
{% endmacro %}


-- ============================================================================
-- Cents to Dollars Conversion
-- ============================================================================
-- Converts amount in cents to dollars with 2 decimal precision

{% macro cents_to_dollars(amount_cents) %}
  CAST({{ amount_cents }} AS DECIMAL(18,2)) / 100
{% endmacro %}


-- ============================================================================
-- Merchant Health Score
-- ============================================================================
-- Calculates merchant health based on dispute rate, refund rate, and failure rate
-- Returns a score from 0-100 (higher = healthier)
-- Weight: 40% dispute rate, 30% refund rate, 30% failure rate

{% macro merchant_health_score(dispute_rate, refund_rate, failure_rate) %}
  GREATEST(0, LEAST(100,
    100 - (
      ({{ dispute_rate }} * 400) +  -- Disputes weighted heavily
      ({{ refund_rate }} * 300) +   -- Refunds weighted moderately
      ({{ failure_rate }} * 300)    -- Failures weighted moderately
    )
  ))
{% endmacro %}


-- ============================================================================
-- Merchant Health Category
-- ============================================================================
-- Classifies merchant health based on health score
-- Thresholds:
--   Excellent: >= 90
--   Good:      >= 70
--   Fair:      >= 50
--   Poor:      < 50

{% macro merchant_health_category(health_score) %}
  CASE
    WHEN {{ health_score }} >= 90 THEN 'excellent'
    WHEN {{ health_score }} >= 70 THEN 'good'
    WHEN {{ health_score }} >= 50 THEN 'fair'
    ELSE 'poor'
  END
{% endmacro %}


-- ============================================================================
-- Payment Status Category
-- ============================================================================
-- Normalizes payment status to standard categories

{% macro payment_status_category(status) %}
  CASE
    WHEN LOWER({{ status }}) IN ('succeeded', 'paid', 'complete', 'completed') THEN 'succeeded'
    WHEN LOWER({{ status }}) IN ('failed', 'failure', 'declined') THEN 'failed'
    WHEN LOWER({{ status }}) IN ('pending', 'processing', 'in_progress') THEN 'pending'
    WHEN LOWER({{ status }}) IN ('refunded', 'partially_refunded') THEN 'refunded'
    WHEN LOWER({{ status }}) IN ('disputed', 'chargeback') THEN 'disputed'
    WHEN LOWER({{ status }}) IN ('canceled', 'cancelled', 'voided') THEN 'canceled'
    ELSE 'unknown'
  END
{% endmacro %}


-- ============================================================================
-- Event Type Category
-- ============================================================================
-- Normalizes event types to standard categories

{% macro event_type_category(event_type) %}
  CASE
    WHEN {{ event_type }} LIKE '%charge%' OR {{ event_type }} LIKE '%payment%succeeded%' THEN 'charge'
    WHEN {{ event_type }} LIKE '%refund%' THEN 'refund'
    WHEN {{ event_type }} LIKE '%dispute%' OR {{ event_type }} LIKE '%chargeback%' THEN 'dispute'
    WHEN {{ event_type }} LIKE '%subscription%' THEN 'subscription'
    WHEN {{ event_type }} LIKE '%failed%' THEN 'failed_payment'
    ELSE 'other'
  END
{% endmacro %}


-- ============================================================================
-- Safe Division
-- ============================================================================
-- Returns 0 when dividing by 0 to avoid errors

{% macro safe_divide(numerator, denominator) %}
  CASE
    WHEN {{ denominator }} = 0 OR {{ denominator }} IS NULL THEN 0
    ELSE CAST({{ numerator }} AS DOUBLE) / {{ denominator }}
  END
{% endmacro %}
