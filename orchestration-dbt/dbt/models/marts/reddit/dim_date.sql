-- ============================================================================
-- Dimension Model: Date Dimension
-- ============================================================================
-- Purpose: Standard date dimension table for time-based analysis
-- Source: Created from date range of all Reddit posts and comments
-- Materialization: Incremental Iceberg table
-- Surrogate Key: date_key (generated from date_day)
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='date_key',
    file_format='iceberg',
    incremental_strategy='merge',
    tags=['dimension', 'reddit', 'date']
  )
}}

WITH all_dates AS (
    -- Get all dates from posts
    SELECT DISTINCT DATE(created_at) AS date_day
    FROM {{ ref('stg_reddit_posts') }}

    {% if is_incremental() %}
        WHERE DATE(created_at) > (SELECT MAX(date_day) FROM {{ this }})
    {% endif %}

    UNION

    -- Get all dates from comments
    SELECT DISTINCT DATE(created_at) AS date_day
    FROM {{ ref('stg_reddit_comments') }}

    {% if is_incremental() %}
        WHERE DATE(created_at) > (SELECT MAX(date_day) FROM {{ this }})
    {% endif %}
),

date_dimension AS (
    SELECT
        -- ====================================================================
        -- Surrogate Key
        -- ====================================================================
        {{ dbt_utils.generate_surrogate_key(['date_day']) }} AS date_key,

        -- ====================================================================
        -- Natural Key
        -- ====================================================================
        date_day,

        -- ====================================================================
        -- Date Attributes
        -- ====================================================================
        EXTRACT(YEAR FROM date_day) AS year,
        EXTRACT(QUARTER FROM date_day) AS quarter,
        EXTRACT(MONTH FROM date_day) AS month,
        EXTRACT(WEEK FROM date_day) AS week_of_year,
        EXTRACT(DAY FROM date_day) AS day_of_month,
        EXTRACT(DAY_OF_WEEK FROM date_day) AS day_of_week,  -- 1=Monday, 7=Sunday
        EXTRACT(DAY_OF_YEAR FROM date_day) AS day_of_year,

        -- ====================================================================
        -- Formatted Labels
        -- ====================================================================
        CASE EXTRACT(DAY_OF_WEEK FROM date_day)
            WHEN 1 THEN 'Monday'
            WHEN 2 THEN 'Tuesday'
            WHEN 3 THEN 'Wednesday'
            WHEN 4 THEN 'Thursday'
            WHEN 5 THEN 'Friday'
            WHEN 6 THEN 'Saturday'
            WHEN 7 THEN 'Sunday'
        END AS day_name,

        CASE EXTRACT(MONTH FROM date_day)
            WHEN 1 THEN 'January'
            WHEN 2 THEN 'February'
            WHEN 3 THEN 'March'
            WHEN 4 THEN 'April'
            WHEN 5 THEN 'May'
            WHEN 6 THEN 'June'
            WHEN 7 THEN 'July'
            WHEN 8 THEN 'August'
            WHEN 9 THEN 'September'
            WHEN 10 THEN 'October'
            WHEN 11 THEN 'November'
            WHEN 12 THEN 'December'
        END AS month_name,

        -- ====================================================================
        -- Flags
        -- ====================================================================
        CASE
            WHEN EXTRACT(DAY_OF_WEEK FROM date_day) IN (6, 7) THEN TRUE
            ELSE FALSE
        END AS is_weekend,

        CASE
            WHEN EXTRACT(DAY_OF_WEEK FROM date_day) BETWEEN 1 AND 5 THEN TRUE
            ELSE FALSE
        END AS is_weekday,

        -- First day of month
        CASE
            WHEN EXTRACT(DAY FROM date_day) = 1 THEN TRUE
            ELSE FALSE
        END AS is_month_start,

        -- Last day of month
        CASE
            WHEN date_day = DATE_ADD('month', 1, DATE_TRUNC('month', date_day)) - INTERVAL '1' DAY THEN TRUE
            ELSE FALSE
        END AS is_month_end,

        -- ====================================================================
        -- Period Labels
        -- ====================================================================
        FORMAT('%04d-Q%d', EXTRACT(YEAR FROM date_day), EXTRACT(QUARTER FROM date_day)) AS quarter_name,
        FORMAT('%04d-%02d', EXTRACT(YEAR FROM date_day), EXTRACT(MONTH FROM date_day)) AS month_year,
        FORMAT('%04d-W%02d', EXTRACT(YEAR FROM date_day), EXTRACT(WEEK FROM date_day)) AS week_year

    FROM all_dates
)

SELECT * FROM date_dimension
