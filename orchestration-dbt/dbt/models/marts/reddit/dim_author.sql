-- ============================================================================
-- Dimension Model: Author Dimension with SCD Type 2
-- ============================================================================
-- Purpose: Author dimension tracking historical changes to author metrics
-- Source: int_reddit_author_stats
-- Materialization: Incremental Iceberg table
-- Surrogate Key: author_key (generated from author + valid_from)
-- SCD Type: Type 2 (track history with valid_from/valid_to/is_current)
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='author_key',
    file_format='iceberg',
    incremental_strategy='merge',
    tags=['dimension', 'reddit', 'author', 'scd-type-2']
  )
}}

WITH author_stats AS (
    SELECT * FROM {{ ref('int_reddit_author_stats') }}
),

author_dimension AS (
    SELECT
        -- ====================================================================
        -- Surrogate Key (includes valid_from for SCD Type 2)
        -- Each version of an author gets a unique key
        -- ====================================================================
        {{ dbt_utils.generate_surrogate_key(['author', 'author_fullname', 'last_seen_at']) }} AS author_key,

        -- ====================================================================
        -- Natural Keys
        -- ====================================================================
        author,
        author_fullname,

        -- ====================================================================
        -- Activity Metrics
        -- ====================================================================
        total_posts,
        total_comments,
        total_activity,

        -- ====================================================================
        -- Engagement Scores
        -- ====================================================================
        total_post_score,
        total_comment_score,
        total_score,
        avg_post_score,
        avg_comment_score,
        avg_score,
        max_post_score,
        max_comment_score,
        max_score,

        -- ====================================================================
        -- Awards and Recognition
        -- ====================================================================
        total_awards,

        -- ====================================================================
        -- Comment-Specific Metrics
        -- ====================================================================
        total_comments_on_posts,
        total_controversiality,
        op_comments_count,  -- Comments on own posts
        avg_comment_depth,

        -- ====================================================================
        -- Content Type Preferences
        -- ====================================================================
        self_posts_count,
        video_posts_count,
        CAST(self_posts_count AS DOUBLE) / NULLIF(total_posts, 0) AS self_post_ratio,
        CAST(video_posts_count AS DOUBLE) / NULLIF(total_posts, 0) AS video_post_ratio,

        -- ====================================================================
        -- Temporal
        -- ====================================================================
        first_seen_at,
        last_seen_at,
        DATE_DIFF('day', first_seen_at, last_seen_at) AS days_active,

        -- ====================================================================
        -- Premium Status
        -- ====================================================================
        is_premium,

        -- ====================================================================
        -- Reputation Score (ML Feature)
        -- ====================================================================
        reputation_score,

        -- ====================================================================
        -- SCD Type 2 Tracking
        -- ====================================================================
        last_seen_at AS valid_from,
        CAST(NULL AS TIMESTAMP) AS valid_to,
        TRUE AS is_current,

        -- ====================================================================
        -- Derived Segments (for analysis)
        -- Use custom macros for maintainability
        -- ====================================================================
        {{ reputation_tier('reputation_score') }} AS reputation_tier,

        {{ activity_type('total_posts', 'total_comments') }} AS activity_type,

        -- ====================================================================
        -- Audit Columns
        -- ====================================================================
        CURRENT_TIMESTAMP AS dw_created_at,
        CURRENT_TIMESTAMP AS dw_updated_at

    FROM author_stats

    {% if is_incremental() %}
        -- For incremental, only process new author versions
        -- New version = author with a last_seen_at newer than any existing version
        WHERE (author, last_seen_at) NOT IN (
            SELECT author, valid_from FROM {{ this }}
        )
    {% endif %}
)

SELECT * FROM author_dimension

-- ============================================================================
-- SCD Type 2 Implementation Notes:
-- ============================================================================
-- This is a simplified SCD Type 2 implementation that creates a new version
-- for each author whenever their stats change (indicated by last_seen_at).
--
-- The author_key surrogate key includes last_seen_at, ensuring each version
-- gets a unique identifier.
--
-- To query current authors:
--   SELECT * FROM dim_author WHERE is_current = TRUE
--
-- To query historical state:
--   SELECT * FROM dim_author
--   WHERE author = 'username'
--     AND timestamp BETWEEN valid_from AND COALESCE(valid_to, CURRENT_TIMESTAMP)
--
-- Future Enhancement:
-- Implement proper SCD Type 2 logic to:
-- 1. Detect changes by comparing new stats with existing current records
-- 2. Close out old versions (set is_current=FALSE, valid_to=new_valid_from)
-- 3. Only insert new versions when actual changes are detected
-- ============================================================================
