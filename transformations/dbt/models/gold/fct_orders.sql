-- ============================================================================
-- EXAMPLE TEMPLATE: Gold Layer Orders Fact Table
-- ============================================================================
-- STATUS: Template/Example - NOT READY FOR USE
--
-- This is an example showing the structure of a Gold layer fact table
-- in a star schema design.
--
-- DO NOT RUN until Bronze and Silver layer models are working.
--
-- Purpose: Order transactions fact table with dimension foreign keys
-- Source: Bronze staging (stg_orders) + Silver dimensions
-- Schema: Star schema with surrogate keys to dimensions
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='order_key',
    file_format='iceberg',
    incremental_strategy='merge',
    partition_by=['order_date_key'],
    tags=['gold', 'fact', 'orders', 'star-schema', 'example']
  )
}}

-- EXAMPLE QUERY STRUCTURE - Update once Bronze and Silver models are ready
WITH source_orders AS (
    SELECT
        order_id,
        order_number,
        customer_id,
        product_id,
        quantity,
        unit_price,
        discount_percent,
        discount_amount,
        tax_amount,
        total_amount,
        shipping_city,
        shipping_state,
        shipping_country,
        order_status,
        order_date,
        shipped_date,
        delivered_date,
        order_date_only,
        order_year,
        order_month,
        days_to_ship,
        days_to_deliver,
        created_at,
        updated_at
    FROM {{ ref('stg_orders') }}

    {% if is_incremental() %}
        -- Only process new/updated orders since last run
        WHERE order_date >= (SELECT MAX(order_date) FROM {{ this }})
           OR updated_at > (SELECT MAX(dw_updated_at) FROM {{ this }})
    {% endif %}
),

-- Join to dimensions to get surrogate keys
orders_with_dimension_keys AS (
    SELECT
        o.order_id,
        o.order_number,

        -- Foreign keys to dimensions (surrogate keys)
        -- Date dimension
        CAST(DATE_FORMAT(o.order_date, '%Y%m%d') AS INTEGER) AS order_date_key,
        CASE
            WHEN o.shipped_date IS NOT NULL
            THEN CAST(DATE_FORMAT(o.shipped_date, '%Y%m%d') AS INTEGER)
            ELSE NULL
        END AS shipped_date_key,
        CASE
            WHEN o.delivered_date IS NOT NULL
            THEN CAST(DATE_FORMAT(o.delivered_date, '%Y%m%d') AS INTEGER)
            ELSE NULL
        END AS delivered_date_key,

        -- Customer dimension (get current version)
        c.customer_key,

        -- Product dimension
        p.product_key,

        -- Degenerate dimensions (attributes that don't warrant their own dimension)
        o.order_id AS order_id_degenerate,
        o.order_number,
        o.shipping_city,
        o.shipping_state,
        o.shipping_country,
        o.order_status,

        -- Measures (numeric facts)
        o.quantity,
        o.unit_price,
        o.discount_percent,
        o.discount_amount,
        o.tax_amount,
        o.total_amount,

        -- Calculated measures
        o.quantity * o.unit_price AS subtotal_amount,
        o.total_amount - o.tax_amount AS pre_tax_amount,

        -- Product cost lookup for profitability analysis
        p.cost AS product_unit_cost,
        (o.unit_price - p.cost) AS unit_margin,
        (o.unit_price - p.cost) * o.quantity AS total_margin,

        -- Time-based measures
        o.days_to_ship,
        o.days_to_deliver,

        -- Derived measures for analysis
        CASE
            WHEN o.days_to_ship <= 1 THEN 'Same/Next Day'
            WHEN o.days_to_ship <= 3 THEN '2-3 Days'
            WHEN o.days_to_ship <= 7 THEN '4-7 Days'
            ELSE 'Over 1 Week'
        END AS shipping_speed_tier,

        CASE
            WHEN o.total_amount < 50 THEN 'Small'
            WHEN o.total_amount < 200 THEN 'Medium'
            WHEN o.total_amount < 1000 THEN 'Large'
            ELSE 'Enterprise'
        END AS order_size_tier,

        -- Status flags
        CASE WHEN LOWER(o.order_status) = 'completed' THEN TRUE ELSE FALSE END AS is_completed,
        CASE WHEN LOWER(o.order_status) = 'cancelled' THEN TRUE ELSE FALSE END AS is_cancelled,
        CASE WHEN LOWER(o.order_status) = 'returned' THEN TRUE ELSE FALSE END AS is_returned,

        -- Timestamps
        o.order_date,
        o.shipped_date,
        o.delivered_date,
        o.created_at AS order_created_at,
        o.updated_at AS order_updated_at,
        CURRENT_TIMESTAMP AS dw_created_at,
        CURRENT_TIMESTAMP AS dw_updated_at

    FROM source_orders o

    -- Join to dimensions to get surrogate keys
    -- Customer dimension (get current version with is_current flag)
    LEFT JOIN {{ ref('dim_customer') }} c
        ON o.customer_id = c.customer_id
        AND c.is_current = TRUE

    -- Product dimension
    LEFT JOIN {{ ref('dim_product') }} p
        ON o.product_id = p.product_id
),

-- Generate surrogate key for fact table
final AS (
    SELECT
        -- Surrogate key for fact table
        {{ dbt_utils.generate_surrogate_key(['order_id']) }} AS order_key,

        -- Dimension foreign keys
        order_date_key,
        shipped_date_key,
        delivered_date_key,
        customer_key,
        product_key,

        -- Degenerate dimensions
        order_id_degenerate,
        order_number,
        shipping_city,
        shipping_state,
        shipping_country,
        order_status,

        -- Measures (facts)
        quantity,
        unit_price,
        discount_percent,
        discount_amount,
        tax_amount,
        total_amount,
        subtotal_amount,
        pre_tax_amount,
        product_unit_cost,
        unit_margin,
        total_margin,
        days_to_ship,
        days_to_deliver,

        -- Derived attributes
        shipping_speed_tier,
        order_size_tier,
        is_completed,
        is_cancelled,
        is_returned,

        -- Timestamps
        order_date,
        shipped_date,
        delivered_date,
        order_created_at,
        order_updated_at,
        dw_created_at,
        dw_updated_at

    FROM orders_with_dimension_keys
)

SELECT * FROM final

-- ============================================================================
-- Star Schema Fact Table Notes:
-- ============================================================================
--
-- This fact table implements the star schema pattern:
--
-- Structure:
-- 1. Surrogate Key: order_key (unique identifier for each fact row)
-- 2. Foreign Keys: Links to dimension tables (customer_key, product_key, date_key)
-- 3. Degenerate Dimensions: Attributes stored in fact table (order_id, order_number)
-- 4. Measures: Numeric facts for aggregation (quantities, amounts, margins)
-- 5. Flags: Boolean indicators for filtering (is_completed, is_cancelled)
--
-- Why Surrogate Keys?
-- - Dimensions use surrogate keys (customer_key) instead of natural keys (customer_id)
-- - Surrogate keys are stable even when natural keys change
-- - For SCD Type 2 dimensions, surrogate keys link to specific versions
-- - Integer keys provide better join performance than varchar keys
--
-- Partitioning:
-- - Partitioned by order_date_key for efficient time-based queries
-- - Queries filtering on date will scan fewer files
-- - Critical for large fact tables with billions of rows
--
-- ============================================================================
-- Usage Examples (Star Schema Queries):
-- ============================================================================
--
-- 1. Monthly revenue by customer segment:
--    SELECT
--        d.year,
--        d.month_name,
--        c.customer_segment,
--        SUM(f.total_amount) AS revenue,
--        COUNT(DISTINCT f.order_key) AS order_count,
--        SUM(f.total_margin) AS gross_profit
--    FROM fct_orders f
--    JOIN dim_date d ON f.order_date_key = d.date_key
--    JOIN dim_customer c ON f.customer_key = c.customer_key
--    WHERE d.year = 2024
--    GROUP BY d.year, d.month_name, c.customer_segment
--
-- 2. Product performance analysis:
--    SELECT
--        p.category,
--        p.subcategory,
--        p.product_name,
--        SUM(f.quantity) AS units_sold,
--        SUM(f.total_amount) AS revenue,
--        SUM(f.total_margin) AS profit,
--        AVG(f.unit_margin) AS avg_unit_margin
--    FROM fct_orders f
--    JOIN dim_product p ON f.product_key = p.product_key
--    WHERE f.is_completed = TRUE
--    GROUP BY p.category, p.subcategory, p.product_name
--    ORDER BY revenue DESC
--
-- 3. Shipping performance metrics:
--    SELECT
--        d.year_month,
--        f.shipping_speed_tier,
--        COUNT(*) AS order_count,
--        AVG(f.days_to_ship) AS avg_days_to_ship,
--        AVG(f.days_to_deliver) AS avg_days_to_deliver,
--        SUM(CASE WHEN f.days_to_ship <= 2 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS pct_fast_shipping
--    FROM fct_orders f
--    JOIN dim_date d ON f.order_date_key = d.date_key
--    WHERE f.is_completed = TRUE
--    GROUP BY d.year_month, f.shipping_speed_tier
--
-- 4. Customer lifetime value (using SCD Type 2):
--    -- This shows how to use historical customer data
--    SELECT
--        c.customer_id,
--        c.customer_name,
--        c.customer_segment,
--        COUNT(DISTINCT f.order_key) AS total_orders,
--        SUM(f.total_amount) AS lifetime_revenue,
--        SUM(f.total_margin) AS lifetime_profit,
--        MIN(f.order_date) AS first_order_date,
--        MAX(f.order_date) AS last_order_date
--    FROM fct_orders f
--    JOIN dim_customer c ON f.customer_key = c.customer_key
--    -- For current customer state, add: WHERE c.is_current = TRUE
--    GROUP BY c.customer_id, c.customer_name, c.customer_segment
--
-- 5. Weekday vs weekend sales:
--    SELECT
--        d.is_weekend,
--        CASE WHEN d.is_weekend THEN 'Weekend' ELSE 'Weekday' END AS day_type,
--        COUNT(*) AS order_count,
--        SUM(f.total_amount) AS revenue,
--        AVG(f.total_amount) AS avg_order_value
--    FROM fct_orders f
--    JOIN dim_date d ON f.order_date_key = d.date_key
--    GROUP BY d.is_weekend
--
-- ============================================================================
-- Performance Optimization:
-- ============================================================================
--
-- 1. Partitioning Strategy:
--    - Fact table is partitioned by order_date_key
--    - Queries filtering on date will be much faster
--    - Consider additional partitioning by region/category for very large tables
--
-- 2. Incremental Loads:
--    - Uses incremental materialization to only process new orders
--    - Merge strategy handles late-arriving updates
--    - Critical for maintaining performance as fact table grows
--
-- 3. Indexing:
--    - Iceberg automatically maintains statistics
--    - Foreign keys benefit from dimension table primary keys
--    - Consider clustering by frequently joined dimensions
--
-- 4. Pre-aggregation:
--    - For very large fact tables, create aggregate fact tables
--    - Example: daily_sales_summary, monthly_revenue_by_product
--    - Trade storage for query performance
--
-- ============================================================================
-- Prerequisites:
-- ============================================================================
--
-- 1. Install dbt-utils package for surrogate_key generation
-- 2. Ensure dimension tables are built first:
--    - dim_customer
--    - dim_product
--    - dim_date
-- 3. Ensure Bronze staging model is working:
--    - stg_orders
--
-- ============================================================================
