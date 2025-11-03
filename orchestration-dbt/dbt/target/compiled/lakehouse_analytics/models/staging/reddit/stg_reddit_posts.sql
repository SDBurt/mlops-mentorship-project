-- ============================================================================
-- Staging Model: Reddit Posts
-- ============================================================================
-- Purpose: Union all Reddit posts from all subreddits into a single staging view
-- Source: Raw posts tables from 5 subreddit datasets
-- Materialization: View (source-conformed, atomic building block)
-- ============================================================================



WITH all_posts AS (
    -- Union posts from all subreddit sources using dbt_utils
    
    

        (
            select
                cast('"lakehouse"."raw_worldnews"."reddit_worldnews_posts"' as varchar) as _dbt_source_relation,

                

            from "lakehouse"."raw_worldnews"."reddit_worldnews_posts"

            
        )

        union all
        

        (
            select
                cast('"lakehouse"."raw_economics"."reddit_economics_posts"' as varchar) as _dbt_source_relation,

                

            from "lakehouse"."raw_economics"."reddit_economics_posts"

            
        )

        union all
        

        (
            select
                cast('"lakehouse"."raw_finance"."reddit_finance_posts"' as varchar) as _dbt_source_relation,

                

            from "lakehouse"."raw_finance"."reddit_finance_posts"

            
        )

        union all
        

        (
            select
                cast('"lakehouse"."raw_wallstreetbets"."reddit_wallstreetbets_posts"' as varchar) as _dbt_source_relation,

                

            from "lakehouse"."raw_wallstreetbets"."reddit_wallstreetbets_posts"

            
        )

        union all
        

        (
            select
                cast('"lakehouse"."raw_investing"."reddit_investing_posts"' as varchar) as _dbt_source_relation,

                

            from "lakehouse"."raw_investing"."reddit_investing_posts"

            
        )

        
),

cleaned_posts AS (
    SELECT
        -- ====================================================================
        -- Identity Fields
        -- ====================================================================
        CAST(id AS VARCHAR) AS post_id,
        CAST(name AS VARCHAR) AS post_name,
        CAST(subreddit AS VARCHAR) AS subreddit,
        FROM_UNIXTIME(CAST(created_utc AS BIGINT)) AS created_at,
        CAST(permalink AS VARCHAR) AS permalink,

        -- ====================================================================
        -- Content Fields
        -- ====================================================================
        CAST(title AS VARCHAR) AS title,
        CAST(selftext AS VARCHAR) AS selftext,
        CAST(url AS VARCHAR) AS url,
        CAST(domain AS VARCHAR) AS domain,

        -- ====================================================================
        -- Engagement Metrics
        -- ====================================================================
        CAST(score AS BIGINT) AS score,
        CAST(upvote_ratio AS DOUBLE) AS upvote_ratio,
        CAST(num_comments AS BIGINT) AS num_comments,
        CAST(num_crossposts AS BIGINT) AS num_crossposts,

        -- ====================================================================
        -- Awards
        -- ====================================================================
        CAST(total_awards_received AS BIGINT) AS total_awards_received,
        CAST(gilded AS BIGINT) AS gilded,

        -- ====================================================================
        -- User Interaction Signals (nullable - user-specific)
        -- ====================================================================
        CAST(clicked AS BOOLEAN) AS clicked,
        CAST(visited AS BOOLEAN) AS visited,
        CAST(saved AS BOOLEAN) AS saved,
        CAST(hidden AS BOOLEAN) AS hidden,

        -- ====================================================================
        -- Author Features
        -- ====================================================================
        CAST(author AS VARCHAR) AS author,
        CAST(author_fullname AS VARCHAR) AS author_fullname,
        CAST(author_premium AS BOOLEAN) AS author_premium,
        CAST(author_flair_text AS VARCHAR) AS author_flair_text,

        -- ====================================================================
        -- Content Type Classification
        -- ====================================================================
        CAST(is_self AS BOOLEAN) AS is_self,
        CAST(is_video AS BOOLEAN) AS is_video,
        CAST(is_gallery AS BOOLEAN) AS is_gallery,
        CAST(post_hint AS VARCHAR) AS post_hint,
        CAST(over_18 AS BOOLEAN) AS over_18,

        -- ====================================================================
        -- Moderation/Quality Flags
        -- ====================================================================
        CAST(stickied AS BOOLEAN) AS stickied,
        CAST(locked AS BOOLEAN) AS locked,
        CAST(archived AS BOOLEAN) AS archived,
        -- Edited is either FALSE or a timestamp
        CASE
            WHEN edited IS NULL OR edited = false THEN FALSE
            WHEN TYPEOF(edited) = 'boolean' THEN edited
            ELSE TRUE
        END AS edited

    FROM all_posts

    -- Data quality filters
    WHERE id IS NOT NULL
      AND subreddit IS NOT NULL
      AND created_utc IS NOT NULL
      AND score IS NOT NULL
)

SELECT * FROM cleaned_posts