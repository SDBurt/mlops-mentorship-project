-- ============================================================================
-- Fact Model: Reddit Posts
-- ============================================================================
-- Purpose: Post fact table with engagement metrics and dimensional foreign keys
-- Source: int_reddit_post_metrics
-- Materialization: Incremental Iceberg table (partitioned by created_date)
-- Surrogate Key: post_key (generated from post_id)
-- Grain: One row per Reddit post
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='post_key',
    file_format='iceberg',
    incremental_strategy='merge',
    partition_by=['created_date'],
    tags=['fact', 'reddit', 'posts']
  )
}}

WITH post_metrics AS (
    SELECT * FROM {{ ref('int_reddit_post_metrics') }}
),

posts_with_dimensions AS (
    SELECT
        p.*,

        -- Join to dimensions to get surrogate keys
        ds.subreddit_key,
        dd.date_key,

        -- For author, join to current version
        -- Note: For full SCD Type 2 support, we'd join on valid_from/valid_to
        -- For now, joining to most recent version
        da.author_key

    FROM post_metrics p

    -- Join to subreddit dimension
    LEFT JOIN {{ ref('dim_subreddit') }} ds
        ON p.subreddit = ds.subreddit

    -- Join to date dimension
    LEFT JOIN {{ ref('dim_date') }} dd
        ON p.created_date = dd.date_day

    -- Join to author dimension (current version)
    LEFT JOIN {{ ref('dim_author') }} da
        ON p.author = da.author
        AND p.author_fullname = da.author_fullname
        AND da.is_current = TRUE

    {% if is_incremental() %}
        -- For incremental, only process new or updated posts
        WHERE p.post_id NOT IN (SELECT post_id FROM {{ this }})
    {% endif %}
),

fact_posts AS (
    SELECT
        -- ====================================================================
        -- Surrogate Key (Primary Key)
        -- ====================================================================
        {{ dbt_utils.generate_surrogate_key(['post_id']) }} AS post_key,

        -- ====================================================================
        -- Natural Key
        -- ====================================================================
        post_id,
        post_name,

        -- ====================================================================
        -- Foreign Keys (Surrogate Keys to Dimensions)
        -- ====================================================================
        subreddit_key,
        author_key,
        date_key,

        -- ====================================================================
        -- Degenerate Dimensions (descriptive attributes on fact)
        -- ====================================================================
        subreddit,  -- Denormalized for convenience
        author,     -- Denormalized for convenience

        -- ====================================================================
        -- Temporal
        -- ====================================================================
        created_at,
        created_date,
        hour_of_day,
        day_of_week,
        is_weekend,

        -- ====================================================================
        -- Content Fields
        -- ====================================================================
        title,
        title_length,
        selftext,
        selftext_length,
        url,
        domain,
        has_url,
        content_type,
        permalink,

        -- ====================================================================
        -- Engagement Metrics (Additive Measures)
        -- ====================================================================
        score,
        num_comments,
        num_crossposts,
        total_awards_received,
        gilded,

        -- ====================================================================
        -- Engagement Ratios (Non-Additive Measures)
        -- ====================================================================
        upvote_ratio,

        -- ====================================================================
        -- Derived Engagement Metrics (for ML/Feast)
        -- ====================================================================
        engagement_score,
        virality_ratio,
        controversy_score,
        quality_score,
        award_ratio,

        -- ====================================================================
        -- Comment Metrics
        -- ====================================================================
        actual_comment_count,  -- From actual comment data
        unique_commenters,
        avg_comment_score,
        max_comment_score,
        time_to_first_comment_minutes,
        comment_velocity_per_hour,
        comment_diversity,

        -- ====================================================================
        -- Content Type Flags
        -- ====================================================================
        is_self,
        is_video,
        is_gallery,
        post_hint,
        over_18,

        -- ====================================================================
        -- Moderation Flags
        -- ====================================================================
        stickied,
        locked,
        archived,
        edited,

        -- ====================================================================
        -- User Interaction Signals (nullable)
        -- ====================================================================
        clicked,
        visited,
        saved,
        hidden,

        -- ====================================================================
        -- Audit Columns
        -- ====================================================================
        CURRENT_TIMESTAMP AS dw_created_at,
        CURRENT_TIMESTAMP AS dw_updated_at

    FROM posts_with_dimensions
)

SELECT * FROM fact_posts

-- ============================================================================
-- Feast Feature Store Integration:
-- ============================================================================
-- This fact table is optimized for Feast feature store:
--
-- Entity: post (key: post_id)
-- Timestamp: created_at
--
-- Feature Groups:
-- 1. Engagement Features:
--    - score, upvote_ratio, num_comments, engagement_score, quality_score
-- 2. Virality Features:
--    - virality_ratio, comment_velocity_per_hour, time_to_first_comment_minutes
-- 3. Content Features:
--    - title_length, content_type, has_url, is_video
-- 4. Temporal Features:
--    - hour_of_day, day_of_week, is_weekend
--
-- Example Feast Feature View:
-- post_engagement_features = FeatureView(
--     name="post_engagement_features",
--     entities=[post_entity],
--     schema=[
--         Field("engagement_score", Float32),
--         Field("quality_score", Float32),
--         ...
--     ],
--     source=TrinoSource(
--         table="lakehouse.gold.fct_posts",
--         timestamp_field="created_at",
--     ),
-- )
-- ============================================================================
