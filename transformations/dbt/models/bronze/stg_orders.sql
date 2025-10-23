-- ============================================================================
-- EXAMPLE TEMPLATE: Bronze Layer Orders Staging Model
-- ============================================================================
-- STATUS: Template/Example - NOT READY FOR USE
--
-- This is an example showing the structure of a Bronze layer staging model.
-- DO NOT RUN until you have configured data sources and ingestion.
--
-- Purpose: Initial transformation, type casting, and data quality checks
-- Source: Raw orders data ingested by Airbyte (to be configured)
-- ============================================================================

{{
  config(
    materialized='view',
    tags=['bronze', 'staging', 'orders', 'example']
  )
}}

-- EXAMPLE QUERY STRUCTURE - Update with actual source table names
WITH source AS (
    -- TODO: Replace with actual source reference once Airbyte is configured
    -- Example: SELECT * FROM lakehouse.bronze.raw_orders

    SELECT
        -- Order identifiers
        CAST(order_id AS VARCHAR) AS order_id,
        CAST(order_number AS VARCHAR) AS order_number,

        -- Foreign keys
        CAST(customer_id AS VARCHAR) AS customer_id,
        CAST(product_id AS VARCHAR) AS product_id,

        -- Order details
        CAST(quantity AS INTEGER) AS quantity,
        CAST(unit_price AS DECIMAL(10,2)) AS unit_price,
        CAST(discount_percent AS DECIMAL(5,2)) AS discount_percent,
        CAST(tax_percent AS DECIMAL(5,2)) AS tax_percent,

        -- Location
        CAST(shipping_city AS VARCHAR) AS shipping_city,
        CAST(shipping_state AS VARCHAR) AS shipping_state,
        CAST(shipping_country AS VARCHAR) AS shipping_country,

        -- Status
        CAST(order_status AS VARCHAR) AS order_status,

        -- Timestamps
        CAST(order_date AS TIMESTAMP) AS order_date,
        CAST(shipped_date AS TIMESTAMP) AS shipped_date,
        CAST(delivered_date AS TIMESTAMP) AS delivered_date,
        CAST(created_at AS TIMESTAMP) AS created_at,
        CAST(updated_at AS TIMESTAMP) AS updated_at,

        -- Airbyte metadata
        _airbyte_ab_id,
        _airbyte_emitted_at,
        _airbyte_normalized_at,
        _airbyte_orders_hashid

    FROM {{ source('raw', 'orders') }}

),

calculated AS (
    SELECT
        order_id,
        order_number,
        customer_id,
        product_id,

        -- Quantities and prices
        quantity,
        unit_price,
        discount_percent,
        tax_percent,

        -- Calculated amounts
        quantity * unit_price AS subtotal_amount,
        (quantity * unit_price) * (discount_percent / 100.0) AS discount_amount,
        ((quantity * unit_price) - ((quantity * unit_price) * (discount_percent / 100.0))) AS amount_after_discount,
        ((quantity * unit_price) - ((quantity * unit_price) * (discount_percent / 100.0))) * (tax_percent / 100.0) AS tax_amount,
        ((quantity * unit_price) - ((quantity * unit_price) * (discount_percent / 100.0))) * (1 + (tax_percent / 100.0)) AS total_amount,

        -- Location
        shipping_city,
        shipping_state,
        UPPER(shipping_country) AS shipping_country,

        -- Status normalization
        LOWER(TRIM(order_status)) AS order_status,

        -- Timestamps
        order_date,
        shipped_date,
        delivered_date,
        created_at,
        updated_at,

        -- Derived date components for partitioning
        DATE(order_date) AS order_date_only,
        YEAR(order_date) AS order_year,
        MONTH(order_date) AS order_month,
        DAY(order_date) AS order_day,
        DAYOFWEEK(order_date) AS order_day_of_week,

        -- Fulfillment metrics
        CASE
            WHEN shipped_date IS NOT NULL
            THEN DATE_DIFF('day', order_date, shipped_date)
            ELSE NULL
        END AS days_to_ship,

        CASE
            WHEN delivered_date IS NOT NULL
            THEN DATE_DIFF('day', order_date, delivered_date)
            ELSE NULL
        END AS days_to_deliver,

        -- Airbyte metadata
        _airbyte_ab_id,
        _airbyte_emitted_at,
        _airbyte_normalized_at

    FROM source

    -- Data quality filters
    WHERE order_id IS NOT NULL
      AND customer_id IS NOT NULL
      AND product_id IS NOT NULL
      AND quantity > 0
      AND unit_price >= 0
      AND order_date IS NOT NULL
)

SELECT * FROM calculated
