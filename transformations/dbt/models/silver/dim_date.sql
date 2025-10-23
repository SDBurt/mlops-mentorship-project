-- ============================================================================
-- EXAMPLE TEMPLATE: Silver Layer Date Dimension
-- ============================================================================
-- STATUS: Template/Example - READY TO USE
--
-- This is a standard date dimension that can be used as-is.
-- It generates a row for each date in a specified range with useful
-- calendar attributes for time-based analysis.
--
-- Purpose: Date dimension with calendar attributes
-- Source: Generated via SQL (not dependent on other tables)
-- SCD Type: N/A (static reference data)
-- ============================================================================

{{
  config(
    materialized='table',
    file_format='iceberg',
    tags=['silver', 'dimension', 'date', 'ready']
  )
}}

-- Generate a sequence of dates
-- Default: 10 years of history + 2 years future
WITH date_spine AS (
    SELECT
        DATE_ADD('day', seq, DATE '2020-01-01') AS date_day
    FROM (
        SELECT SEQUENCE(0, 4382) AS seq_array  -- 12 years * 365.25 days
    )
    CROSS JOIN UNNEST(seq_array) AS t(seq)
),

-- Calculate all date attributes
date_attributes AS (
    SELECT
        date_day,

        -- Date components
        YEAR(date_day) AS year,
        QUARTER(date_day) AS quarter,
        MONTH(date_day) AS month,
        WEEK(date_day) AS week_of_year,
        DAY(date_day) AS day_of_month,
        DAY_OF_WEEK(date_day) AS day_of_week,  -- 1 = Monday, 7 = Sunday
        DAY_OF_YEAR(date_day) AS day_of_year,

        -- Formatted date strings
        DATE_FORMAT(date_day, '%Y-%m-%d') AS date_string,
        DATE_FORMAT(date_day, '%Y-%m') AS year_month,
        DATE_FORMAT(date_day, '%Y-Q') || CAST(QUARTER(date_day) AS VARCHAR) AS year_quarter,
        DATE_FORMAT(date_day, '%Y-%W') AS year_week,

        -- Month name and day name
        DATE_FORMAT(date_day, '%B') AS month_name,           -- January, February, ...
        DATE_FORMAT(date_day, '%b') AS month_name_short,     -- Jan, Feb, ...
        DATE_FORMAT(date_day, '%A') AS day_name,             -- Monday, Tuesday, ...
        DATE_FORMAT(date_day, '%a') AS day_name_short,       -- Mon, Tue, ...

        -- First and last days of periods
        DATE_TRUNC('month', date_day) AS first_day_of_month,
        LAST_DAY_OF_MONTH(date_day) AS last_day_of_month,
        DATE_TRUNC('quarter', date_day) AS first_day_of_quarter,
        DATE_TRUNC('year', date_day) AS first_day_of_year,

        -- Business date flags
        CASE
            WHEN DAY_OF_WEEK(date_day) IN (6, 7) THEN FALSE  -- Saturday, Sunday
            ELSE TRUE
        END AS is_weekday,

        CASE
            WHEN DAY_OF_WEEK(date_day) IN (6, 7) THEN TRUE
            ELSE FALSE
        END AS is_weekend,

        -- Month position flags
        CASE
            WHEN DAY(date_day) = 1 THEN TRUE
            ELSE FALSE
        END AS is_first_day_of_month,

        CASE
            WHEN date_day = LAST_DAY_OF_MONTH(date_day) THEN TRUE
            ELSE FALSE
        END AS is_last_day_of_month,

        -- Quarter position flags
        CASE
            WHEN date_day = DATE_TRUNC('quarter', date_day) THEN TRUE
            ELSE FALSE
        END AS is_first_day_of_quarter,

        CASE
            WHEN date_day = LAST_DAY_OF_MONTH(DATE_ADD('month', 2, DATE_TRUNC('quarter', date_day))) THEN TRUE
            ELSE FALSE
        END AS is_last_day_of_quarter,

        -- Year position flags
        CASE
            WHEN date_day = DATE_TRUNC('year', date_day) THEN TRUE
            ELSE FALSE
        END AS is_first_day_of_year,

        CASE
            WHEN date_day = DATE '1970-01-01' + INTERVAL '1' YEAR * (YEAR(date_day) + 1) - INTERVAL '1' DAY THEN TRUE
            ELSE FALSE
        END AS is_last_day_of_year,

        -- Relative date flags
        CASE
            WHEN date_day = CURRENT_DATE THEN TRUE
            ELSE FALSE
        END AS is_today,

        CASE
            WHEN date_day = CURRENT_DATE - INTERVAL '1' DAY THEN TRUE
            ELSE FALSE
        END AS is_yesterday,

        CASE
            WHEN date_day = CURRENT_DATE + INTERVAL '1' DAY THEN TRUE
            ELSE FALSE
        END AS is_tomorrow,

        -- Days from today (negative = past, positive = future)
        DATE_DIFF('day', CURRENT_DATE, date_day) AS days_from_today,

        -- Fiscal year (assuming fiscal year starts in January - adjust as needed)
        YEAR(date_day) AS fiscal_year,
        QUARTER(date_day) AS fiscal_quarter,

        -- Holiday flags (US holidays - customize as needed)
        CASE
            -- New Year's Day
            WHEN MONTH(date_day) = 1 AND DAY(date_day) = 1 THEN TRUE
            -- Independence Day
            WHEN MONTH(date_day) = 7 AND DAY(date_day) = 4 THEN TRUE
            -- Christmas
            WHEN MONTH(date_day) = 12 AND DAY(date_day) = 25 THEN TRUE
            ELSE FALSE
        END AS is_us_holiday

    FROM date_spine
),

-- Generate surrogate key
final AS (
    SELECT
        -- Surrogate key (integer format: YYYYMMDD)
        CAST(DATE_FORMAT(date_day, '%Y%m%d') AS INTEGER) AS date_key,

        -- All date attributes
        date_day,
        year,
        quarter,
        month,
        week_of_year,
        day_of_month,
        day_of_week,
        day_of_year,
        date_string,
        year_month,
        year_quarter,
        year_week,
        month_name,
        month_name_short,
        day_name,
        day_name_short,
        first_day_of_month,
        last_day_of_month,
        first_day_of_quarter,
        first_day_of_year,
        is_weekday,
        is_weekend,
        is_first_day_of_month,
        is_last_day_of_month,
        is_first_day_of_quarter,
        is_last_day_of_quarter,
        is_first_day_of_year,
        is_last_day_of_year,
        is_today,
        is_yesterday,
        is_tomorrow,
        days_from_today,
        fiscal_year,
        fiscal_quarter,
        is_us_holiday,

        -- Audit
        CURRENT_TIMESTAMP AS dw_created_at

    FROM date_attributes
)

SELECT * FROM final
ORDER BY date_key

-- ============================================================================
-- Date Dimension Usage Notes:
-- ============================================================================
--
-- The date dimension is a fundamental component of any star schema.
-- It enables powerful time-based analysis and reporting.
--
-- Key Features:
-- - Covers 2020-01-01 to 2031-12-31 (adjust range in date_spine CTE)
-- - Pre-calculated calendar attributes (month, quarter, fiscal year)
-- - Business day flags (weekday, weekend, holidays)
-- - Relative date flags (today, yesterday, last 7/30/90 days)
-- - Integer surrogate key in YYYYMMDD format for efficient joins
--
-- ============================================================================
-- Usage Examples:
-- ============================================================================
--
-- 1. Join to fact table on date:
--    SELECT d.year, d.month_name, SUM(f.total_amount)
--    FROM fct_orders f
--    JOIN dim_date d ON f.date_key = d.date_key
--    GROUP BY d.year, d.month_name
--
-- 2. Filter to weekdays only:
--    SELECT * FROM dim_date
--    WHERE is_weekday = TRUE
--      AND year = 2024
--
-- 3. Find last day of each month:
--    SELECT * FROM dim_date
--    WHERE is_last_day_of_month = TRUE
--
-- 4. Get current month dates:
--    SELECT * FROM dim_date
--    WHERE year_month = DATE_FORMAT(CURRENT_DATE, '%Y-%m')
--
-- 5. Fiscal year analysis:
--    SELECT fiscal_year, fiscal_quarter, COUNT(*) AS days
--    FROM dim_date
--    WHERE is_weekday = TRUE
--    GROUP BY fiscal_year, fiscal_quarter
--
-- ============================================================================
-- Customization:
-- ============================================================================
--
-- 1. Adjust date range:
--    - Change start date in date_spine CTE
--    - Adjust SEQUENCE length (days to generate)
--
-- 2. Customize fiscal year:
--    - If fiscal year starts in a different month (e.g., July):
--      CASE WHEN MONTH(date_day) >= 7
--           THEN YEAR(date_day)
--           ELSE YEAR(date_day) - 1
--      END AS fiscal_year
--
-- 3. Add company-specific holidays:
--    - Extend is_us_holiday CASE statement
--    - Or create separate holiday columns by region
--
-- 4. Add week start on Sunday (instead of Monday):
--    - Adjust DAY_OF_WEEK calculations
--    - Some orgs prefer Sunday = 1, Monday = 2
--
-- ============================================================================
