-- ============================================================================
-- EXAMPLE TEMPLATE: Bronze Layer Customer Staging Model
-- ============================================================================
-- STATUS: Template/Example - NOT READY FOR USE
--
-- This is an example showing the structure of a Bronze layer staging model.
-- DO NOT RUN until you have:
--   1. Configured Airbyte data sources
--   2. Ingested raw data into Iceberg tables
--   3. Updated source table references below
--
-- Purpose: Initial transformation and type casting from raw ingested data
-- Source: Raw customer data ingested by Airbyte (to be configured)
-- ============================================================================

{{
  config(
    materialized='view',
    tags=['bronze', 'staging', 'customers', 'example']
  )
}}

-- EXAMPLE QUERY STRUCTURE - Update with actual source table names
WITH source AS (
    -- TODO: Replace with actual source reference once Airbyte is configured
    -- Example: SELECT * FROM lakehouse.bronze.raw_customers

    SELECT
        -- Placeholder data structure - update based on actual source schema
        CAST(customer_id AS VARCHAR) AS customer_id,
        CAST(email AS VARCHAR) AS email,
        CAST(first_name AS VARCHAR) AS first_name,
        CAST(last_name AS VARCHAR) AS last_name,
        CAST(phone AS VARCHAR) AS phone,
        CAST(address_line1 AS VARCHAR) AS address_line1,
        CAST(address_line2 AS VARCHAR) AS address_line2,
        CAST(city AS VARCHAR) AS city,
        CAST(state AS VARCHAR) AS state,
        CAST(postal_code AS VARCHAR) AS postal_code,
        CAST(country AS VARCHAR) AS country,
        CAST(created_at AS TIMESTAMP) AS created_at,
        CAST(updated_at AS TIMESTAMP) AS updated_at,

        -- Airbyte metadata columns
        _airbyte_ab_id,
        _airbyte_emitted_at,
        _airbyte_normalized_at,
        _airbyte_customers_hashid

    FROM {{ source('raw', 'customers') }}

),

cleaned AS (
    SELECT
        customer_id,

        -- Email normalization
        LOWER(TRIM(email)) AS email,

        -- Name formatting
        INITCAP(TRIM(first_name)) AS first_name,
        INITCAP(TRIM(last_name)) AS last_name,
        TRIM(first_name) || ' ' || TRIM(last_name) AS full_name,

        -- Contact information
        phone,

        -- Address components
        address_line1,
        address_line2,
        city,
        state,
        postal_code,
        UPPER(country) AS country,

        -- Timestamps
        created_at,
        updated_at,

        -- Airbyte metadata for data quality tracking
        _airbyte_ab_id,
        _airbyte_emitted_at,
        _airbyte_normalized_at

    FROM source

    -- Data quality filters
    WHERE customer_id IS NOT NULL
      AND email IS NOT NULL
      AND email LIKE '%@%'  -- Basic email validation
)

SELECT * FROM cleaned
