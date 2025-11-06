-- ============================================================================
-- Dimension Model: Subreddit Dimension
-- ============================================================================
-- Purpose: Subreddit dimension with metadata and community metrics
-- Source: stg_reddit_subreddits
-- Materialization: Incremental Iceberg table (replace/merge)
-- Surrogate Key: subreddit_key (generated from subreddit)
-- SCD Type: Type 1 (replace - metadata changes are overwritten)
-- ============================================================================

{{
  config(
    materialized='incremental',
    unique_key='subreddit_key',
    file_format='iceberg',
    incremental_strategy='merge',
    tags=['dimension', 'reddit', 'subreddit']
  )
}}

WITH subreddit_dimension AS (
    SELECT
        -- ====================================================================
        -- Surrogate Key
        -- ====================================================================
        {{ dbt_utils.generate_surrogate_key(['subreddit']) }} AS subreddit_key,

        -- ====================================================================
        -- Natural Key
        -- ====================================================================
        subreddit,
        subreddit_id,
        subreddit_name,

        -- ====================================================================
        -- Descriptive Attributes
        -- ====================================================================
        title,
        public_description,
        description,
        header_title,

        -- ====================================================================
        -- Community Metrics
        -- ====================================================================
        subscribers,
        active_users,

        -- ====================================================================
        -- Temporal
        -- ====================================================================
        created_at AS subreddit_created_at,

        -- ====================================================================
        -- Community Settings
        -- ====================================================================
        is_over_18,
        subreddit_type,
        submission_type,

        -- ====================================================================
        -- Moderation Settings
        -- ====================================================================
        spoilers_enabled,
        allow_images,
        allow_videos,
        allow_polls,

        -- ====================================================================
        -- Community Flags
        -- ====================================================================
        quarantine,
        user_is_banned,
        user_is_muted,
        user_is_moderator,

        -- ====================================================================
        -- Audit Columns
        -- ====================================================================
        CURRENT_TIMESTAMP AS dw_created_at,
        CURRENT_TIMESTAMP AS dw_updated_at

    FROM {{ ref('stg_reddit_subreddits') }}

    {% if is_incremental() %}
        -- For incremental, only process new or updated subreddits
        WHERE subreddit NOT IN (SELECT subreddit FROM {{ this }})
           OR subreddit_id NOT IN (SELECT subreddit_id FROM {{ this }})
    {% endif %}
)

SELECT * FROM subreddit_dimension
