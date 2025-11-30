-- ============================================================================
-- Dimension Model: Date
-- ============================================================================
-- Purpose: Date dimension for time-based analysis
-- Materialization: Table (static dimension, regenerated on full refresh)
-- ============================================================================

{{
  config(
    materialized='table',
    format='PARQUET',
    tags=['marts', 'payments', 'dimensions']
  )
}}

-- Generate date spine from 2020 to 2030
WITH date_spine AS (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2020-01-01' as date)",
        end_date="cast('2030-12-31' as date)"
    ) }}
),

dates AS (
    SELECT
        CAST(date_day AS DATE) AS date_key
    FROM date_spine
)

SELECT
    -- Date key (surrogate key is the date itself)
    date_key,

    -- Date components
    YEAR(date_key) AS year,
    QUARTER(date_key) AS quarter,
    MONTH(date_key) AS month,
    WEEK(date_key) AS week_of_year,
    DAY(date_key) AS day_of_month,
    day_of_week(date_key) AS day_of_week,
    day_of_year(date_key) AS day_of_year,

    -- Date names
    DATE_FORMAT(date_key, 'EEEE') AS day_name,
    DATE_FORMAT(date_key, 'MMMM') AS month_name,
    DATE_FORMAT(date_key, 'MMM') AS month_name_short,

    -- Fiscal periods (assuming fiscal year = calendar year)
    YEAR(date_key) AS fiscal_year,
    QUARTER(date_key) AS fiscal_quarter,

    -- Flags (day_of_week: 1=Monday, 7=Sunday in Trino)
    CASE WHEN day_of_week(date_key) IN (6, 7) THEN TRUE ELSE FALSE END AS is_weekend,
    CASE WHEN day_of_week(date_key) NOT IN (6, 7) THEN TRUE ELSE FALSE END AS is_weekday,

    -- Period keys for grouping
    CONCAT(CAST(YEAR(date_key) AS VARCHAR), '-', LPAD(CAST(MONTH(date_key) AS VARCHAR), 2, '0')) AS year_month,
    CONCAT(CAST(YEAR(date_key) AS VARCHAR), '-Q', CAST(QUARTER(date_key) AS VARCHAR)) AS year_quarter,
    CAST(YEAR(date_key) AS VARCHAR) AS year_str,

    -- ISO week
    WEEK(date_key) AS iso_week,
    CONCAT(CAST(YEAR(date_key) AS VARCHAR), '-W', LPAD(CAST(WEEK(date_key) AS VARCHAR), 2, '0')) AS iso_year_week

FROM dates
