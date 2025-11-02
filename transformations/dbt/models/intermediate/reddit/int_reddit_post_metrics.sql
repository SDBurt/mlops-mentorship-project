-- ============================================================================
-- Intermediate Model: Reddit Post Engagement Metrics
-- ============================================================================
-- Purpose: Calculate derived engagement metrics for posts
-- Used by: fct_posts (Gold layer)
-- Materialization: Ephemeral (not persisted, used as CTE)
-- ============================================================================

{{
  config(
    materialized='ephemeral',
    tags=['intermediate', 'reddit', 'posts', 'metrics']
  )
}}

WITH post_comments AS (
    -- Get comment counts and metrics per post
    SELECT
        post_id,
        COUNT(DISTINCT comment_id) AS total_comments,
        AVG(score) AS avg_comment_score,
        MAX(score) AS max_comment_score,
        MIN(created_at) AS first_comment_at,
        MAX(created_at) AS last_comment_at,
        COUNT(DISTINCT author) AS unique_commenters

    FROM {{ ref('stg_reddit_comments') }}
    GROUP BY post_id
),

post_metrics AS (
    SELECT
        p.*,

        -- Join comment metrics
        COALESCE(c.total_comments, 0) AS actual_comment_count,
        c.avg_comment_score,
        c.max_comment_score,
        c.unique_commenters,

        -- ====================================================================
        -- Temporal Features
        -- ====================================================================
        EXTRACT(HOUR FROM p.created_at) AS hour_of_day,
        EXTRACT(DAY_OF_WEEK FROM p.created_at) AS day_of_week,
        CASE
            WHEN EXTRACT(DAY_OF_WEEK FROM p.created_at) IN (6, 7) THEN TRUE
            ELSE FALSE
        END AS is_weekend,
        DATE(p.created_at) AS created_date,

        -- Time to first comment (minutes)
        CASE
            WHEN c.first_comment_at IS NOT NULL THEN
                DATE_DIFF('minute', p.created_at, c.first_comment_at)
            ELSE NULL
        END AS time_to_first_comment_minutes,

        -- Comment velocity (comments per hour)
        CASE
            WHEN c.last_comment_at IS NOT NULL AND c.last_comment_at != c.first_comment_at THEN
                CAST(c.total_comments AS DOUBLE) / NULLIF(
                    DATE_DIFF('minute', c.first_comment_at, c.last_comment_at) / 60.0,
                    0
                )
            ELSE NULL
        END AS comment_velocity_per_hour,

        -- ====================================================================
        -- Content Features
        -- ====================================================================
        LENGTH(p.title) AS title_length,
        LENGTH(p.selftext) AS selftext_length,
        CASE
            WHEN p.url IS NOT NULL AND p.url != '' THEN TRUE
            ELSE FALSE
        END AS has_url,
        {{ content_type('p.is_self', 'p.is_video', 'p.is_gallery', 'p.url') }} AS content_type,

        -- ====================================================================
        -- Engagement Scores (Derived Metrics for ML)
        -- Use custom macros for maintainability
        -- ====================================================================

        -- Engagement score: weighted combination of score, comments, awards
        {{ engagement_score('p.score', 'p.num_comments', 'p.total_awards_received') }} AS engagement_score,

        -- Virality ratio: comments per score (high = viral discussion)
        CAST(p.num_comments AS DOUBLE) / NULLIF(CAST(p.score AS DOUBLE), 0) AS virality_ratio,

        -- Controversy score: low upvote_ratio + high engagement = controversial
        CASE
            WHEN p.upvote_ratio < 0.7 AND p.num_comments > 10 THEN
                (1.0 - p.upvote_ratio) * LOG(CAST(p.num_comments AS DOUBLE))
            ELSE 0
        END AS controversy_score,

        -- Quality score: high upvote ratio + good score
        p.upvote_ratio * LOG(CAST(p.score + 1 AS DOUBLE)) AS quality_score,

        -- Award ratio: awards per score (prestigious content)
        CAST(COALESCE(p.total_awards_received, 0) AS DOUBLE) /
            NULLIF(CAST(p.score AS DOUBLE), 0) AS award_ratio,

        -- Comment diversity: unique commenters / total comments
        CAST(COALESCE(c.unique_commenters, 0) AS DOUBLE) /
            NULLIF(CAST(c.total_comments AS DOUBLE), 0) AS comment_diversity

    FROM {{ ref('stg_reddit_posts') }} p
    LEFT JOIN post_comments c
        ON p.post_id = c.post_id
)

SELECT * FROM post_metrics
