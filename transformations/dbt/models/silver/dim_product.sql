-- ============================================================================
-- EXAMPLE TEMPLATE: Silver Layer Product Dimension
-- ============================================================================
-- STATUS: Template/Example - NOT READY FOR USE
--
-- This is an example showing the structure of a Silver layer dimension table.
--
-- DO NOT RUN until Bronze layer models are working.
--
-- Purpose: Product dimension with category hierarchy and metrics
-- Source: Bronze layer staging model (stg_products)
-- SCD Type: Type 1 (overwrite changes - simpler than Type 2)
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='product_key',
    file_format='iceberg',
    incremental_strategy='merge',
    tags=['silver', 'dimension', 'product', 'scd-type-1', 'example']
  )
}}

-- EXAMPLE QUERY STRUCTURE - Update once Bronze models are ready
WITH source_products AS (
    SELECT
        product_id,
        sku,
        product_name,
        description,
        category,
        subcategory,
        brand,
        list_price,
        cost,
        margin_amount,
        margin_percent,
        price_tier,
        stock_quantity,
        reorder_level,
        stock_status,
        color,
        size,
        weight_kg,
        is_active,
        discontinued_date,
        is_currently_available,
        created_at,
        updated_at,
        days_since_created
    FROM {{ ref('stg_products') }}

    {% if is_incremental() %}
        -- Only process records that have changed since last run
        WHERE updated_at > (SELECT MAX(product_updated_at) FROM {{ this }})
    {% endif %}
),

-- Calculate product performance metrics from orders
product_metrics AS (
    SELECT
        p.product_id,

        -- Sales metrics
        COUNT(DISTINCT o.order_id) AS total_orders,
        SUM(o.quantity) AS total_quantity_sold,
        SUM(o.total_amount) AS total_revenue,
        AVG(o.unit_price) AS average_selling_price,

        -- Temporal metrics
        MIN(o.order_date) AS first_order_date,
        MAX(o.order_date) AS last_order_date,
        DATE_DIFF('day', MAX(o.order_date), CURRENT_DATE) AS days_since_last_sale,

        -- Calculate sell-through rate
        COUNT(DISTINCT DATE(o.order_date)) AS days_with_sales

    FROM source_products p
    LEFT JOIN {{ ref('stg_orders') }} o
        ON p.product_id = o.product_id

    GROUP BY p.product_id
),

-- Combine product data with metrics
enriched_products AS (
    SELECT
        p.product_id,

        -- Product identifiers
        p.sku,
        p.product_name,
        p.description,

        -- Category hierarchy (for drill-down analysis)
        p.category,
        p.subcategory,
        p.brand,

        -- Pricing
        p.list_price,
        p.cost,
        p.margin_amount,
        p.margin_percent,
        p.price_tier,

        -- Inventory
        p.stock_quantity,
        p.reorder_level,
        p.stock_status,

        -- Physical attributes
        p.color,
        p.size,
        p.weight_kg,

        -- Status
        p.is_active,
        p.discontinued_date,
        p.is_currently_available,

        -- Product lifecycle
        CASE
            WHEN m.total_orders IS NULL OR m.total_orders = 0 THEN 'Never Sold'
            WHEN p.days_since_created <= 30 THEN 'New Launch'
            WHEN m.days_since_last_sale <= 30 THEN 'Active'
            WHEN m.days_since_last_sale <= 90 THEN 'Slow Moving'
            WHEN p.is_active = FALSE OR p.discontinued_date IS NOT NULL THEN 'Discontinued'
            ELSE 'Inactive'
        END AS product_lifecycle_stage,

        -- Performance classification (ABC analysis)
        CASE
            WHEN COALESCE(m.total_revenue, 0) >= 50000 THEN 'A - High Value'
            WHEN COALESCE(m.total_revenue, 0) >= 10000 THEN 'B - Medium Value'
            WHEN COALESCE(m.total_revenue, 0) > 0 THEN 'C - Low Value'
            ELSE 'D - No Sales'
        END AS abc_classification,

        -- Velocity (sales frequency)
        CASE
            WHEN COALESCE(m.days_with_sales, 0) >= 250 THEN 'Fast Moving'  -- Sells almost every day
            WHEN COALESCE(m.days_with_sales, 0) >= 100 THEN 'Regular'
            WHEN COALESCE(m.days_with_sales, 0) >= 30 THEN 'Slow Moving'
            WHEN COALESCE(m.days_with_sales, 0) > 0 THEN 'Very Slow'
            ELSE 'No Movement'
        END AS velocity_classification,

        -- Inventory health
        CASE
            WHEN p.stock_quantity = 0 THEN 'Out of Stock'
            WHEN p.stock_quantity <= p.reorder_level THEN 'Reorder Needed'
            WHEN p.stock_quantity > p.reorder_level * 5 THEN 'Overstocked'
            ELSE 'Healthy'
        END AS inventory_health,

        -- Sales metrics
        COALESCE(m.total_orders, 0) AS total_orders,
        COALESCE(m.total_quantity_sold, 0) AS total_quantity_sold,
        COALESCE(m.total_revenue, 0) AS total_revenue,
        COALESCE(m.average_selling_price, 0) AS average_selling_price,
        m.first_order_date,
        m.last_order_date,
        COALESCE(m.days_since_last_sale, 999999) AS days_since_last_sale,

        -- Calculated profitability
        CASE
            WHEN COALESCE(m.total_quantity_sold, 0) > 0
            THEN (p.list_price - p.cost) * m.total_quantity_sold
            ELSE 0
        END AS total_profit,

        -- Days on market
        p.days_since_created,

        -- Timestamps
        p.created_at AS product_created_at,
        p.updated_at AS product_updated_at,
        CURRENT_TIMESTAMP AS dw_created_at,
        CURRENT_TIMESTAMP AS dw_updated_at

    FROM source_products p
    LEFT JOIN product_metrics m
        ON p.product_id = m.product_id
),

-- Generate surrogate key
final AS (
    SELECT
        -- Surrogate key (hash of product_id for consistency)
        {{ dbt_utils.generate_surrogate_key(['product_id']) }} AS product_key,

        -- Natural key
        product_id,

        -- All other columns
        sku,
        product_name,
        description,
        category,
        subcategory,
        brand,
        list_price,
        cost,
        margin_amount,
        margin_percent,
        price_tier,
        stock_quantity,
        reorder_level,
        stock_status,
        color,
        size,
        weight_kg,
        is_active,
        discontinued_date,
        is_currently_available,
        product_lifecycle_stage,
        abc_classification,
        velocity_classification,
        inventory_health,
        total_orders,
        total_quantity_sold,
        total_revenue,
        average_selling_price,
        first_order_date,
        last_order_date,
        days_since_last_sale,
        total_profit,
        days_since_created,
        product_created_at,
        product_updated_at,
        dw_created_at,
        dw_updated_at

    FROM enriched_products
)

SELECT * FROM final

-- ============================================================================
-- SCD Type 1 Implementation Notes:
-- ============================================================================
-- This model uses SCD Type 1, which means changes OVERWRITE the existing
-- record. Historical values are NOT preserved.
--
-- Why Type 1 for Products?
-- - Product attributes (price, description) change frequently
-- - Historical prices are less critical (can be tracked in fact tables)
-- - Simpler to query (always get current state)
-- - Better performance (no history to filter)
--
-- If you need historical product prices or attributes, consider:
-- 1. Switching to SCD Type 2 (like dim_customer example)
-- 2. Creating a separate price history table
-- 3. Storing effective prices in the fact table
--
-- ============================================================================
-- Usage Examples:
-- ============================================================================
--
-- 1. Find all active high-value products:
--    SELECT * FROM dim_product
--    WHERE is_currently_available = TRUE
--      AND abc_classification = 'A - High Value'
--
-- 2. Identify products needing reorder:
--    SELECT * FROM dim_product
--    WHERE inventory_health = 'Reorder Needed'
--      AND is_active = TRUE
--
-- 3. Find slow-moving inventory:
--    SELECT * FROM dim_product
--    WHERE velocity_classification IN ('Slow Moving', 'Very Slow')
--      AND stock_quantity > 0
--
-- 4. Category performance analysis:
--    SELECT category, subcategory,
--           SUM(total_revenue) AS category_revenue,
--           AVG(margin_percent) AS avg_margin
--    FROM dim_product
--    GROUP BY category, subcategory
--    ORDER BY category_revenue DESC
--
-- ============================================================================
