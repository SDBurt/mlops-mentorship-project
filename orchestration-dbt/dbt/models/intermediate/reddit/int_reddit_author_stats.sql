-- ============================================================================
-- Intermediate Model: Reddit Author Statistics
-- ============================================================================
-- Purpose: Aggregate author metrics from posts and comments
-- Used by: dim_author (Silver layer)
-- Materialization: Ephemeral (not persisted, used as CTE)
-- ============================================================================

{{
  config(
    materialized='ephemeral',
    tags=['intermediate', 'reddit', 'authors']
  )
}}

WITH post_metrics AS (
    SELECT
        author,
        author_fullname,

        -- Post counts
        COUNT(DISTINCT post_id) AS total_posts,

        -- Engagement metrics from posts
        SUM(score) AS total_post_score,
        AVG(score) AS avg_post_score,
        MAX(score) AS max_post_score,
        SUM(num_comments) AS total_post_comments,
        SUM(total_awards_received) AS total_post_awards,

        -- Temporal
        MIN(created_at) AS first_post_at,
        MAX(created_at) AS last_post_at,

        -- Content flags
        SUM(CASE WHEN is_self THEN 1 ELSE 0 END) AS self_posts_count,
        SUM(CASE WHEN is_video THEN 1 ELSE 0 END) AS video_posts_count,

        -- Premium status (take most recent)
        ARBITRARY(author_premium) AS is_premium

    FROM {{ ref('stg_reddit_posts') }}
    WHERE author IS NOT NULL
      AND author != '[deleted]'
      AND author != 'AutoModerator'
    GROUP BY author, author_fullname
),

comment_metrics AS (
    SELECT
        author,
        author_fullname,

        -- Comment counts
        COUNT(DISTINCT comment_id) AS total_comments,

        -- Engagement metrics from comments
        SUM(score) AS total_comment_score,
        AVG(score) AS avg_comment_score,
        MAX(score) AS max_comment_score,
        SUM(total_awards_received) AS total_comment_awards,
        SUM(controversiality) AS total_controversiality,

        -- Temporal
        MIN(created_at) AS first_comment_at,
        MAX(created_at) AS last_comment_at,

        -- Thread participation
        SUM(CASE WHEN is_submitter THEN 1 ELSE 0 END) AS op_comments_count,
        AVG(depth) AS avg_comment_depth

    FROM {{ ref('stg_reddit_comments') }}
    WHERE author IS NOT NULL
      AND author != '[deleted]'
      AND author != 'AutoModerator'
    GROUP BY author, author_fullname
),

combined_metrics AS (
    SELECT
        COALESCE(p.author, c.author) AS author,
        COALESCE(p.author_fullname, c.author_fullname) AS author_fullname,

        -- Activity counts
        COALESCE(p.total_posts, 0) AS total_posts,
        COALESCE(c.total_comments, 0) AS total_comments,
        COALESCE(p.total_posts, 0) + COALESCE(c.total_comments, 0) AS total_activity,

        -- Engagement scores
        COALESCE(p.total_post_score, 0) AS total_post_score,
        COALESCE(c.total_comment_score, 0) AS total_comment_score,
        COALESCE(p.total_post_score, 0) + COALESCE(c.total_comment_score, 0) AS total_score,

        -- Average scores
        p.avg_post_score,
        c.avg_comment_score,
        (COALESCE(p.total_post_score, 0) + COALESCE(c.total_comment_score, 0)) /
            NULLIF(COALESCE(p.total_posts, 0) + COALESCE(c.total_comments, 0), 0) AS avg_score,

        -- Max scores
        p.max_post_score,
        c.max_comment_score,
        GREATEST(COALESCE(p.max_post_score, 0), COALESCE(c.max_comment_score, 0)) AS max_score,

        -- Awards
        COALESCE(p.total_post_awards, 0) + COALESCE(c.total_comment_awards, 0) AS total_awards,

        -- Comment metrics
        COALESCE(p.total_post_comments, 0) AS total_comments_on_posts,
        c.total_controversiality,
        c.op_comments_count,
        c.avg_comment_depth,

        -- Content type preferences
        p.self_posts_count,
        p.video_posts_count,

        -- Temporal
        CASE
            WHEN p.first_post_at IS NULL THEN c.first_comment_at
            WHEN c.first_comment_at IS NULL THEN p.first_post_at
            ELSE LEAST(p.first_post_at, c.first_comment_at)
        END AS first_seen_at,
        CASE
            WHEN p.last_post_at IS NULL THEN c.last_comment_at
            WHEN c.last_comment_at IS NULL THEN p.last_post_at
            ELSE GREATEST(p.last_post_at, c.last_comment_at)
        END AS last_seen_at,

        -- Premium status
        COALESCE(p.is_premium, FALSE) AS is_premium,

        -- Derived reputation score (simple formula)
        -- Reputation = (total_score * 0.7) + (total_awards * 100) + (total_activity * 0.3)
        (COALESCE(p.total_post_score, 0) + COALESCE(c.total_comment_score, 0)) * 0.7 +
        (COALESCE(p.total_post_awards, 0) + COALESCE(c.total_comment_awards, 0)) * 100 +
        (COALESCE(p.total_posts, 0) + COALESCE(c.total_comments, 0)) * 0.3 AS reputation_score

    FROM post_metrics p
    FULL OUTER JOIN comment_metrics c
        ON p.author = c.author
        AND p.author_fullname = c.author_fullname
)

SELECT * FROM combined_metrics
