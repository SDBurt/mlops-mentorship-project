-- ============================================================================
-- EXAMPLE TEMPLATE: Silver Layer Customer Dimension
-- ============================================================================
-- STATUS: Template/Example - NOT READY FOR USE
--
-- This is an example showing the structure of a Silver layer dimension table
-- with Slowly Changing Dimension (SCD) Type 2 tracking.
--
-- DO NOT RUN until Bronze layer models are working.
--
-- Purpose: Customer dimension with historical tracking
-- Source: Bronze layer staging model (stg_customers)
-- SCD Type: Type 2 (track history with valid_from/valid_to)
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='customer_key',
    file_format='iceberg',
    incremental_strategy='merge',
    tags=['silver', 'dimension', 'customer', 'scd-type-2', 'example']
  )
}}

-- EXAMPLE QUERY STRUCTURE - Update once Bronze models are ready
WITH source_customers AS (
    SELECT
        customer_id,
        email,
        first_name,
        last_name,
        full_name,
        phone,
        address_line1,
        address_line2,
        city,
        state,
        postal_code,
        country,
        created_at,
        updated_at
    FROM {{ ref('stg_customers') }}

    {% if is_incremental() %}
        -- Only process records that have changed since last run
        WHERE updated_at > (SELECT MAX(valid_from) FROM {{ this }})
    {% endif %}
),

-- Calculate customer metrics from orders
customer_metrics AS (
    SELECT
        c.customer_id,

        -- Lifetime value metrics
        COALESCE(SUM(o.total_amount), 0) AS lifetime_value,
        COUNT(DISTINCT o.order_id) AS total_orders,
        AVG(o.total_amount) AS average_order_value,

        -- Temporal metrics
        MIN(o.order_date) AS first_order_date,
        MAX(o.order_date) AS last_order_date,
        DATE_DIFF('day', MAX(o.order_date), CURRENT_TIMESTAMP) AS days_since_last_order,

        -- Recency, Frequency, Monetary for RFM segmentation
        DATE_DIFF('day', MAX(o.order_date), CURRENT_DATE) AS recency_days,
        COUNT(DISTINCT o.order_id) AS frequency_count,
        SUM(o.total_amount) AS monetary_value

    FROM source_customers c
    LEFT JOIN {{ ref('stg_orders') }} o
        ON c.customer_id = o.customer_id

    GROUP BY c.customer_id
),

-- Combine customer data with metrics
enriched_customers AS (
    SELECT
        c.customer_id,

        -- Customer attributes
        c.email,
        c.first_name,
        c.last_name,
        c.full_name,
        c.phone,

        -- Address components
        c.address_line1,
        c.address_line2,
        c.city,
        c.state,
        c.postal_code,
        c.country,

        -- Customer segmentation based on lifetime value
        CASE
            WHEN COALESCE(m.lifetime_value, 0) >= 10000 THEN 'Enterprise'
            WHEN COALESCE(m.lifetime_value, 0) >= 1000 THEN 'SMB'
            WHEN COALESCE(m.lifetime_value, 0) >= 100 THEN 'Individual'
            WHEN COALESCE(m.lifetime_value, 0) > 0 THEN 'Trial'
            ELSE 'Prospect'
        END AS customer_segment,

        -- Lifecycle stage
        CASE
            WHEN m.total_orders IS NULL OR m.total_orders = 0 THEN 'Prospect'
            WHEN m.total_orders = 1 THEN 'New'
            WHEN m.days_since_last_order <= 90 THEN 'Active'
            WHEN m.days_since_last_order <= 180 THEN 'At Risk'
            ELSE 'Churned'
        END AS lifecycle_stage,

        -- RFM Score (simplified - 1 to 5 scale for each dimension)
        CASE
            WHEN m.recency_days <= 30 THEN 5
            WHEN m.recency_days <= 60 THEN 4
            WHEN m.recency_days <= 90 THEN 3
            WHEN m.recency_days <= 180 THEN 2
            ELSE 1
        END AS rfm_recency_score,

        CASE
            WHEN m.frequency_count >= 20 THEN 5
            WHEN m.frequency_count >= 10 THEN 4
            WHEN m.frequency_count >= 5 THEN 3
            WHEN m.frequency_count >= 2 THEN 2
            ELSE 1
        END AS rfm_frequency_score,

        CASE
            WHEN m.monetary_value >= 10000 THEN 5
            WHEN m.monetary_value >= 5000 THEN 4
            WHEN m.monetary_value >= 1000 THEN 3
            WHEN m.monetary_value >= 100 THEN 2
            ELSE 1
        END AS rfm_monetary_score,

        -- Customer metrics
        COALESCE(m.lifetime_value, 0) AS lifetime_value,
        COALESCE(m.total_orders, 0) AS total_orders,
        COALESCE(m.average_order_value, 0) AS average_order_value,
        m.first_order_date,
        m.last_order_date,
        COALESCE(m.days_since_last_order, 999999) AS days_since_last_order,

        -- Timestamps for SCD Type 2
        c.updated_at AS valid_from,
        CAST(NULL AS TIMESTAMP) AS valid_to,
        TRUE AS is_current,

        -- Audit timestamps
        c.created_at AS customer_created_at,
        c.updated_at AS customer_updated_at,
        CURRENT_TIMESTAMP AS dw_created_at,
        CURRENT_TIMESTAMP AS dw_updated_at

    FROM source_customers c
    LEFT JOIN customer_metrics m
        ON c.customer_id = m.customer_id
),

-- Generate surrogate key
final AS (
    SELECT
        -- Surrogate key (combination of customer_id + valid_from for uniqueness)
        {{ dbt_utils.generate_surrogate_key(['customer_id', 'valid_from']) }} AS customer_key,

        -- Natural key
        customer_id,

        -- All other columns
        email,
        first_name,
        last_name,
        full_name,
        phone,
        address_line1,
        address_line2,
        city,
        state,
        postal_code,
        country,
        customer_segment,
        lifecycle_stage,
        rfm_recency_score,
        rfm_frequency_score,
        rfm_monetary_score,
        -- Composite RFM score (concatenation)
        CAST(rfm_recency_score AS VARCHAR) || CAST(rfm_frequency_score AS VARCHAR) || CAST(rfm_monetary_score AS VARCHAR) AS rfm_score,
        lifetime_value,
        total_orders,
        average_order_value,
        first_order_date,
        last_order_date,
        days_since_last_order,
        valid_from,
        valid_to,
        is_current,
        customer_created_at,
        customer_updated_at,
        dw_created_at,
        dw_updated_at

    FROM enriched_customers
)

SELECT * FROM final

-- ============================================================================
-- SCD Type 2 Implementation Notes:
-- ============================================================================
-- This model tracks historical changes to customer records.
--
-- How it works:
-- 1. When a customer's attributes change (e.g., address, segment):
--    - The old record's valid_to is set to the change timestamp
--    - The old record's is_current is set to FALSE
--    - A new record is inserted with the updated values
--    - The new record's valid_from is set to the change timestamp
--    - The new record's is_current is set to TRUE
--
-- 2. To query current customers:
--    SELECT * FROM dim_customer WHERE is_current = TRUE
--
-- 3. To query historical state:
--    SELECT * FROM dim_customer
--    WHERE customer_id = 'CUST123'
--      AND '2024-01-15' BETWEEN valid_from AND COALESCE(valid_to, CURRENT_TIMESTAMP)
--
-- 4. The surrogate key (customer_key) uniquely identifies each version
--    of a customer record, while customer_id is the natural key that
--    ties all versions together.
--
-- ============================================================================
-- Prerequisites:
-- ============================================================================
-- 1. Install dbt-utils package:
--    - Add to packages.yml: dbt-utils: 1.1.1
--    - Run: dbt deps
--
-- 2. Ensure Bronze models are working:
--    - stg_customers must be populated
--    - stg_orders must be populated (for metrics)
--
-- 3. For production, add SCD Type 2 merge logic to handle updates
--    (this example inserts new versions but doesn't close old ones)
--
-- ============================================================================
