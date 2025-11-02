-- ============================================================================
-- Staging Model: Reddit Subreddits
-- ============================================================================
-- Purpose: Union all Reddit subreddit metadata from all sources
-- Source: Raw subreddit metadata tables from 5 subreddit datasets
-- Materialization: View (source-conformed, atomic building block)
-- ============================================================================

{{
  config(
    materialized='view',
    tags=['staging', 'reddit', 'subreddits', 'metadata']
  )
}}

WITH all_subreddits AS (
    -- Union subreddit metadata from all sources using dbt_utils
    {{ dbt_utils.union_relations(
        relations=[
            source('raw_worldnews', 'reddit_worldnews_subreddit'),
            source('raw_economics', 'reddit_economics_subreddit'),
            source('raw_finance', 'reddit_finance_subreddit'),
            source('raw_wallstreetbets', 'reddit_wallstreetbets_subreddit'),
            source('raw_investing', 'reddit_investing_subreddit')
        ]
    ) }}
),

cleaned_subreddits AS (
    SELECT
        -- ====================================================================
        -- Identity Fields
        -- ====================================================================
        CAST(id AS VARCHAR) AS subreddit_id,
        CAST(name AS VARCHAR) AS subreddit_name,  -- Full name (prefixed with t5_)
        CAST(display_name AS VARCHAR) AS subreddit,  -- Display name (e.g., "worldnews")

        -- ====================================================================
        -- Descriptive Fields
        -- ====================================================================
        CAST(title AS VARCHAR) AS title,
        CAST(public_description AS VARCHAR) AS public_description,
        CAST(description AS VARCHAR) AS description,
        CAST(header_title AS VARCHAR) AS header_title,

        -- ====================================================================
        -- Community Metrics
        -- ====================================================================
        CAST(subscribers AS BIGINT) AS subscribers,
        CAST(accounts_active AS BIGINT) AS active_users,

        -- ====================================================================
        -- Temporal Fields
        -- ====================================================================
        FROM_UNIXTIME(CAST(created_utc AS BIGINT)) AS created_at,

        -- ====================================================================
        -- Community Settings
        -- ====================================================================
        CAST(over18 AS BOOLEAN) AS is_over_18,
        CAST(subreddit_type AS VARCHAR) AS subreddit_type,  -- public, private, restricted, etc.
        CAST(submission_type AS VARCHAR) AS submission_type,  -- any, link, self

        -- ====================================================================
        -- Moderation Settings
        -- ====================================================================
        CAST(spoilers_enabled AS BOOLEAN) AS spoilers_enabled,
        CAST(allow_images AS BOOLEAN) AS allow_images,
        CAST(allow_videos AS BOOLEAN) AS allow_videos,
        CAST(allow_polls AS BOOLEAN) AS allow_polls,

        -- ====================================================================
        -- Community Flags
        -- ====================================================================
        CAST(quarantine AS BOOLEAN) AS quarantine,
        CAST(user_is_banned AS BOOLEAN) AS user_is_banned,
        CAST(user_is_muted AS BOOLEAN) AS user_is_muted,
        CAST(user_is_moderator AS BOOLEAN) AS user_is_moderator

    FROM all_subreddits

    -- Data quality filters
    WHERE id IS NOT NULL
      AND display_name IS NOT NULL
)

SELECT * FROM cleaned_subreddits
