-- ============================================================================
-- EXAMPLE TEMPLATE: Bronze Layer Products Staging Model
-- ============================================================================
-- STATUS: Template/Example - NOT READY FOR USE
--
-- This is an example showing the structure of a Bronze layer staging model.
-- DO NOT RUN until you have configured data sources and ingestion.
--
-- Purpose: Initial transformation, type casting, and categorization
-- Source: Raw product data ingested by Airbyte (to be configured)
-- ============================================================================

{{
  config(
    materialized='view',
    tags=['bronze', 'staging', 'products', 'example']
  )
}}

-- EXAMPLE QUERY STRUCTURE - Update with actual source table names
WITH source AS (
    -- TODO: Replace with actual source reference once Airbyte is configured
    -- Example: SELECT * FROM lakehouse.bronze.raw_products

    SELECT
        -- Product identifiers
        CAST(product_id AS VARCHAR) AS product_id,
        CAST(sku AS VARCHAR) AS sku,

        -- Product details
        CAST(product_name AS VARCHAR) AS product_name,
        CAST(description AS VARCHAR) AS description,
        CAST(category AS VARCHAR) AS category,
        CAST(subcategory AS VARCHAR) AS subcategory,
        CAST(brand AS VARCHAR) AS brand,

        -- Pricing
        CAST(list_price AS DECIMAL(10,2)) AS list_price,
        CAST(cost AS DECIMAL(10,2)) AS cost,

        -- Inventory
        CAST(stock_quantity AS INTEGER) AS stock_quantity,
        CAST(reorder_level AS INTEGER) AS reorder_level,

        -- Attributes
        CAST(color AS VARCHAR) AS color,
        CAST(size AS VARCHAR) AS size,
        CAST(weight_kg AS DECIMAL(8,2)) AS weight_kg,

        -- Status
        CAST(is_active AS BOOLEAN) AS is_active,
        CAST(discontinued_date AS DATE) AS discontinued_date,

        -- Timestamps
        CAST(created_at AS TIMESTAMP) AS created_at,
        CAST(updated_at AS TIMESTAMP) AS updated_at,

        -- Airbyte metadata
        _airbyte_ab_id,
        _airbyte_emitted_at,
        _airbyte_normalized_at,
        _airbyte_products_hashid

    FROM {{ source('raw', 'products') }}

),

enriched AS (
    SELECT
        product_id,
        sku,

        -- Product information
        TRIM(product_name) AS product_name,
        description,

        -- Category hierarchy
        INITCAP(TRIM(category)) AS category,
        INITCAP(TRIM(subcategory)) AS subcategory,
        INITCAP(TRIM(brand)) AS brand,

        -- Pricing calculations
        list_price,
        cost,
        list_price - cost AS margin_amount,
        CASE
            WHEN list_price > 0
            THEN ((list_price - cost) / list_price) * 100
            ELSE 0
        END AS margin_percent,

        -- Price tier classification
        CASE
            WHEN list_price < 20 THEN 'Budget'
            WHEN list_price < 100 THEN 'Mid-Range'
            WHEN list_price < 500 THEN 'Premium'
            ELSE 'Luxury'
        END AS price_tier,

        -- Inventory metrics
        stock_quantity,
        reorder_level,
        CASE
            WHEN stock_quantity <= 0 THEN 'Out of Stock'
            WHEN stock_quantity <= reorder_level THEN 'Low Stock'
            ELSE 'In Stock'
        END AS stock_status,

        -- Attributes
        color,
        size,
        weight_kg,

        -- Status flags
        is_active,
        discontinued_date,
        CASE
            WHEN is_active = true AND discontinued_date IS NULL THEN true
            ELSE false
        END AS is_currently_available,

        -- Timestamps
        created_at,
        updated_at,

        -- Product lifecycle
        DATE_DIFF('day', created_at, CURRENT_TIMESTAMP) AS days_since_created,

        -- Airbyte metadata
        _airbyte_ab_id,
        _airbyte_emitted_at,
        _airbyte_normalized_at

    FROM source

    -- Data quality filters
    WHERE product_id IS NOT NULL
      AND product_name IS NOT NULL
)

SELECT * FROM enriched
