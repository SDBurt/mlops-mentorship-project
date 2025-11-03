-- ============================================================================
-- Dimension Model: Date Dimension (using date_spine)
-- ============================================================================
-- Purpose: Standard date dimension table using dbt_utils.date_spine
-- Source: Generated date range (not dependent on data)
-- Materialization: Table (persisted for performance)
-- Surrogate Key: date_key (generated from date_day)
--
-- This version uses date_spine to generate a continuous date range,
-- which is more robust than deriving dates from data.
-- ============================================================================



WITH date_spine AS (
    -- Generate continuous date range using dbt_utils
    -- Adjust start_date and end_date based on your needs
    





with rawdata as (

    

    

    with p as (
        select 0 as generated_number union all select 1
    ), unioned as (

    select

    
    p0.generated_number * power(2, 0)
     + 
    
    p1.generated_number * power(2, 1)
     + 
    
    p2.generated_number * power(2, 2)
     + 
    
    p3.generated_number * power(2, 3)
     + 
    
    p4.generated_number * power(2, 4)
     + 
    
    p5.generated_number * power(2, 5)
     + 
    
    p6.generated_number * power(2, 6)
     + 
    
    p7.generated_number * power(2, 7)
     + 
    
    p8.generated_number * power(2, 8)
     + 
    
    p9.generated_number * power(2, 9)
     + 
    
    p10.generated_number * power(2, 10)
     + 
    
    p11.generated_number * power(2, 11)
    
    
    + 1
    as generated_number

    from

    
    p as p0
     cross join 
    
    p as p1
     cross join 
    
    p as p2
     cross join 
    
    p as p3
     cross join 
    
    p as p4
     cross join 
    
    p as p5
     cross join 
    
    p as p6
     cross join 
    
    p as p7
     cross join 
    
    p as p8
     cross join 
    
    p as p9
     cross join 
    
    p as p10
     cross join 
    
    p as p11
    
    

    )

    select *
    from unioned
    where generated_number <= 2497
    order by generated_number



),

all_periods as (

    select (
        date_add('day', row_number() over (order by 1) - 1, DATE '2020-01-01')
    ) as date_day
    from rawdata

),

filtered as (

    select *
    from all_periods
    where date_day <= current_date + interval '365' day

)

select * from filtered


),

date_dimension AS (
    SELECT
        -- ====================================================================
        -- Surrogate Key
        -- ====================================================================
        lower(to_hex(md5(to_utf8(cast(coalesce(cast(date_day as varchar), '') as varchar))))) AS date_key,

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

    FROM date_spine
)

SELECT * FROM date_dimension

-- ============================================================================
-- Benefits of using date_spine:
-- ============================================================================
-- 1. Continuous date range - no gaps in dates
-- 2. Not dependent on data - works even if no data exists for certain dates
-- 3. Can generate future dates for forecasting
-- 4. Consistent grain (one row per day)
-- 5. More efficient than deriving from fact tables
-- ============================================================================