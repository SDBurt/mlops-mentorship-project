-- ============================================================================
-- Fact Model: Reddit Comments
-- ============================================================================
-- Purpose: Comment fact table with engagement metrics and dimensional foreign keys
-- Source: stg_reddit_comments
-- Materialization: Incremental Iceberg table (partitioned by created_date)
-- Surrogate Key: comment_key (generated from comment_id)
-- Grain: One row per Reddit comment
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='comment_key',
    file_format='iceberg',
    incremental_strategy='merge',
    partition_by=['created_date'],
    tags=['fact', 'reddit', 'comments']
  )
}}

WITH comments_with_dimensions AS (
    SELECT
        c.*,

        -- Temporal extraction
        DATE(c.created_at) AS created_date,
        EXTRACT(HOUR FROM c.created_at) AS hour_of_day,
        EXTRACT(DAY_OF_WEEK FROM c.created_at) AS day_of_week,
        CASE
            WHEN EXTRACT(DAY_OF_WEEK FROM c.created_at) IN (6, 7) THEN TRUE
            ELSE FALSE
        END AS is_weekend,

        -- Content features
        LENGTH(c.body) AS body_length,

        -- Join to post fact to get post_key
        fp.post_key,

        -- Join to subreddit dimension
        ds.subreddit_key,

        -- Join to date dimension
        dd.date_key,

        -- Join to author dimension (comment author - current version)
        da_comment.author_key AS author_key,

        -- Join to parent author dimension (for parent comment/post author)
        -- If parent is a post, get the post's author
        -- If parent is a comment, get that comment's author
        CASE
            WHEN c.parent_type = 'post' THEN fp.author_key
            WHEN c.parent_type = 'comment' THEN da_parent.author_key
            ELSE NULL
        END AS parent_author_key

    FROM {{ ref('stg_reddit_comments') }} c

    -- Join to post fact
    LEFT JOIN {{ ref('fct_posts') }} fp
        ON c.post_id = fp.post_id

    -- Join to subreddit dimension
    LEFT JOIN {{ ref('dim_subreddit') }} ds
        ON c.subreddit = ds.subreddit

    -- Join to date dimension
    LEFT JOIN {{ ref('dim_date') }} dd
        ON DATE(c.created_at) = dd.date_day

    -- Join to comment author dimension (current version)
    LEFT JOIN {{ ref('dim_author') }} da_comment
        ON c.author = da_comment.author
        AND c.author_fullname = da_comment.author_fullname
        AND da_comment.is_current = TRUE

    -- Join to parent comment (for parent_author_key)
    LEFT JOIN {{ ref('stg_reddit_comments') }} c_parent
        ON c.parent_id_clean = c_parent.comment_id
        AND c.parent_type = 'comment'

    -- Join to parent author dimension
    LEFT JOIN {{ ref('dim_author') }} da_parent
        ON c_parent.author = da_parent.author
        AND c_parent.author_fullname = da_parent.author_fullname
        AND da_parent.is_current = TRUE

    {% if is_incremental() %}
        -- For incremental, only process new comments
        WHERE c.comment_id NOT IN (SELECT comment_id FROM {{ this }})
    {% endif %}
),

fact_comments AS (
    SELECT
        -- ====================================================================
        -- Surrogate Key (Primary Key)
        -- ====================================================================
        {{ dbt_utils.generate_surrogate_key(['comment_id']) }} AS comment_key,

        -- ====================================================================
        -- Natural Key
        -- ====================================================================
        comment_id,
        comment_name,

        -- ====================================================================
        -- Foreign Keys (Surrogate Keys to Dimensions and Facts)
        -- ====================================================================
        post_key,              -- FK to fct_posts
        subreddit_key,         -- FK to dim_subreddit
        author_key,            -- FK to dim_author (comment author)
        parent_author_key,     -- FK to dim_author (parent author) - nullable
        date_key,              -- FK to dim_date

        -- ====================================================================
        -- Degenerate Dimensions (descriptive attributes on fact)
        -- ====================================================================
        subreddit,  -- Denormalized for convenience
        author,     -- Denormalized for convenience

        -- ====================================================================
        -- Thread Relationships
        -- ====================================================================
        link_id,
        post_id,
        parent_id,
        parent_type,
        parent_id_clean,
        depth,

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
        body,
        body_length,
        permalink,

        -- ====================================================================
        -- Engagement Metrics (Additive Measures)
        -- ====================================================================
        score,
        ups,
        downs,
        controversiality,
        total_awards_received,
        gilded,

        -- ====================================================================
        -- Author Context
        -- ====================================================================
        is_submitter,  -- True if comment author is OP

        -- ====================================================================
        -- Moderation Flags
        -- ====================================================================
        stickied,
        distinguished,  -- moderator, admin, special, NULL
        score_hidden,
        edited,

        -- ====================================================================
        -- Audit Columns
        -- ====================================================================
        CURRENT_TIMESTAMP AS dw_created_at,
        CURRENT_TIMESTAMP AS dw_updated_at

    FROM comments_with_dimensions
)

SELECT * FROM fact_comments

-- ============================================================================
-- Feast Feature Store Integration:
-- ============================================================================
-- This fact table is optimized for Feast feature store:
--
-- Entity: comment (key: comment_id)
-- Timestamp: created_at
--
-- Feature Groups:
-- 1. Engagement Features:
--    - score, ups, downs, controversiality
-- 2. Thread Features:
--    - depth, is_submitter, parent_type
-- 3. Content Features:
--    - body_length
-- 4. Temporal Features:
--    - hour_of_day, day_of_week, is_weekend
-- 5. Author Context:
--    - is_submitter, distinguished
--
-- Example Feast Feature View:
-- comment_engagement_features = FeatureView(
--     name="comment_engagement_features",
--     entities=[comment_entity],
--     schema=[
--         Field("score", Int64),
--         Field("controversiality", Int64),
--         Field("depth", Int64),
--         ...
--     ],
--     source=TrinoSource(
--         table="lakehouse.gold.fct_comments",
--         timestamp_field="created_at",
--     ),
-- )
--
-- Cross-Entity Features:
-- - Join comment_entity with post_entity via post_key
-- - Join comment_entity with author_entity via author_key
-- ============================================================================
