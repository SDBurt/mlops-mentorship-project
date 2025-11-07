-- ============================================================================
-- Staging Model: Reddit Comments
-- ============================================================================
-- Purpose: Union all Reddit comments from all subreddits into a single staging view
-- Source: Raw comments tables from 5 subreddit datasets
-- Materialization: View (source-conformed, atomic building block)
-- ============================================================================

{{
  config(
    materialized='view',
    tags=['staging', 'reddit', 'comments']
  )
}}

WITH all_comments AS (
    -- Union comments from all subreddit sources using dbt_utils
    {{ dbt_utils.union_relations(
        relations=[
            source('raw_worldnews', 'reddit_worldnews_comments'),
            source('raw_economics', 'reddit_economics_comments'),
            source('raw_finance', 'reddit_finance_comments'),
            source('raw_wallstreetbets', 'reddit_wallstreetbets_comments'),
            source('raw_investing', 'reddit_investing_comments')
        ]
    ) }}
),

cleaned_comments AS (
    SELECT
        -- ====================================================================
        -- Identity Fields
        -- ====================================================================
        CAST(id AS VARCHAR) AS comment_id,
        CAST(name AS VARCHAR) AS comment_name,
        CAST(subreddit AS VARCHAR) AS subreddit,
        FROM_UNIXTIME(CAST(created_utc AS BIGINT)) AS created_at,
        CAST(permalink AS VARCHAR) AS permalink,

        -- ====================================================================
        -- Threading (Relationships)
        -- Parse link_id and parent_id to extract IDs without type prefix (t3_, t1_)
        -- link_id: Always starts with "t3_" (post type)
        -- parent_id: Starts with "t3_" (post) or "t1_" (comment)
        -- ====================================================================
        CAST(link_id AS VARCHAR) AS link_id,
        -- Extract post ID from link_id (remove "t3_" prefix)
        CASE
            WHEN SUBSTR(link_id, 1, 3) = 't3_' THEN SUBSTR(link_id, 4)
            ELSE link_id
        END AS post_id,

        CAST(parent_id AS VARCHAR) AS parent_id,
        -- Determine parent type (post or comment)
        CASE
            WHEN SUBSTR(parent_id, 1, 3) = 't3_' THEN 'post'
            WHEN SUBSTR(parent_id, 1, 3) = 't1_' THEN 'comment'
            ELSE 'unknown'
        END AS parent_type,
        -- Extract parent ID (remove type prefix)
        CASE
            WHEN SUBSTR(parent_id, 1, 3) IN ('t3_', 't1_') THEN SUBSTR(parent_id, 4)
            ELSE parent_id
        END AS parent_id_clean,

        CAST(depth AS BIGINT) AS depth,

        -- ====================================================================
        -- Content Fields
        -- ====================================================================
        CAST(body AS VARCHAR) AS body,

        -- ====================================================================
        -- Engagement Metrics
        -- ====================================================================
        CAST(score AS BIGINT) AS score,
        CAST(ups AS BIGINT) AS ups,
        CAST(downs AS BIGINT) AS downs,
        CAST(controversiality AS BIGINT) AS controversiality,

        -- ====================================================================
        -- Awards
        -- ====================================================================
        CAST(total_awards_received AS BIGINT) AS total_awards_received,
        CAST(gilded AS BIGINT) AS gilded,

        -- ====================================================================
        -- Author Features
        -- ====================================================================
        CAST(author AS VARCHAR) AS author,
        CAST(author_fullname AS VARCHAR) AS author_fullname,
        CAST(author_premium AS BOOLEAN) AS author_premium,
        CAST(author_flair_text AS VARCHAR) AS author_flair_text,
        CAST(is_submitter AS BOOLEAN) AS is_submitter,  -- True if author is OP

        -- ====================================================================
        -- Moderation/Quality Flags
        -- ====================================================================
        CAST(stickied AS BOOLEAN) AS stickied,
        CAST(distinguished AS VARCHAR) AS distinguished,  -- moderator, admin, special, NULL
        CAST(score_hidden AS BOOLEAN) AS score_hidden,
        -- Edited is either FALSE or a timestamp
        CASE
            WHEN edited IS NULL OR edited = false THEN FALSE
            WHEN TYPEOF(edited) = 'boolean' THEN edited
            ELSE TRUE
        END AS edited

    FROM all_comments

    -- Data quality filters
    WHERE id IS NOT NULL
      AND subreddit IS NOT NULL
      AND created_utc IS NOT NULL
      AND link_id IS NOT NULL  -- Must have parent post
)

SELECT * FROM cleaned_comments
