"""
Reddit data source using PRAW (Python Reddit API Wrapper).

Extracts posts and comments from specified subreddits and persists
to Iceberg tables via dagster-iceberg IO manager.
"""

import praw
import pandas as pd
from dagster import asset, AssetExecutionContext
from datetime import datetime
import os


def create_reddit_client() -> praw.Reddit:
    """
    Create authenticated Reddit client using PRAW.

    Credentials are read from environment variables:
    - REDDIT_CLIENT_ID: Reddit API client ID
    - REDDIT_CLIENT_SECRET: Reddit API client secret
    - REDDIT_USER_AGENT: User-Agent string

    Returns:
        Authenticated PRAW Reddit instance

    Raises:
        ValueError: If required environment variables are missing
    """
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "lakehouse:v1.0.0 (by /u/dataengineer)")

    if not client_id or not client_secret:
        raise ValueError(
            "Reddit credentials not found. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET "
            "environment variables. See https://www.reddit.com/prefs/apps"
        )

    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
    )


@asset(
    key_prefix=["data", "reddit"],
    io_manager_key="iceberg_io_manager",
    metadata={
        "partition_expr": "created_utc",  # Iceberg partition column
    },
    group_name="reddit_ingestion",
    compute_kind="api",
)
def reddit_posts(context: AssetExecutionContext) -> pd.DataFrame:
    """
    Extract Reddit posts using PRAW and persist to Iceberg table.

    The dagster-iceberg IO manager automatically handles:
    - Table creation (lakehouse.data.reddit_posts)
    - Schema inference from DataFrame
    - Partitioning by created_utc
    - Upserts based on 'id' column

    Args:
        context: Dagster asset execution context

    Returns:
        DataFrame with Reddit post data

    Raises:
        ValueError: If Reddit credentials are not configured
        Exception: If API request fails
    """
    # Configuration - modify these values as needed
    subreddit = "dataengineering"
    time_filter = "day"
    limit = 100

    context.log.info(f"Extracting posts from r/{subreddit} (time_filter={time_filter}, limit={limit})")

    reddit = create_reddit_client()

    posts_data = []
    for post in reddit.subreddit(subreddit).top(time_filter=time_filter, limit=limit):
        posts_data.append({
            # Identity
            "id": post.id,
            "subreddit": post.subreddit.display_name,
            "created_utc": datetime.fromtimestamp(post.created_utc),
            "permalink": f"https://reddit.com{post.permalink}",

            # Content
            "title": post.title,
            "selftext": post.selftext if post.selftext else None,
            "url": post.url,
            "domain": post.domain,

            # Engagement metrics
            "score": post.score,
            "upvote_ratio": post.upvote_ratio,
            "num_comments": post.num_comments,

            # Author
            "author": str(post.author) if post.author else "[deleted]",

            # Content type
            "is_self": post.is_self,
            "is_video": post.is_video,
            "over_18": post.over_18,

            # Moderation
            "stickied": post.stickied,
            "locked": post.locked,
            "archived": post.archived,
        })

    df = pd.DataFrame(posts_data)

    # Convert timestamp to microsecond precision (Iceberg requirement)
    if len(df) > 0:
        df['created_utc'] = pd.to_datetime(df['created_utc']).dt.as_unit('us')

        # Cast integer columns to int32 to match Iceberg schema expectations
        # Pandas defaults to int64 (long), but Iceberg tables use int32 (int)
        if 'score' in df.columns:
            df['score'] = df['score'].astype('int32')
        if 'num_comments' in df.columns:
            df['num_comments'] = df['num_comments'].astype('int32')

    context.log.info(f"Extracted {len(df)} posts from r/{subreddit}")

    # Add metadata to the asset
    if len(df) > 0:
        context.add_output_metadata({
            "num_records": len(df),
            "subreddit": subreddit,
            "time_filter": time_filter,
            "date_range": f"{df['created_utc'].min()} to {df['created_utc'].max()}",
        })
    else:
        context.add_output_metadata({
            "num_records": 0,
            "subreddit": subreddit,
            "time_filter": time_filter,
            "date_range": "No data",
        })

    return df


@asset(
    key_prefix=["data", "reddit"],
    io_manager_key="iceberg_io_manager",
    metadata={
        "partition_expr": "created_utc",  # Iceberg partition column
    },
    deps=[reddit_posts],  # Depends on posts asset
    group_name="reddit_ingestion",
    compute_kind="api",
)
def reddit_comments(context: AssetExecutionContext) -> pd.DataFrame:
    """
    Extract Reddit comments from top posts using PRAW.

    The dagster-iceberg IO manager automatically handles:
    - Table creation (lakehouse.data.reddit_comments)
    - Schema inference from DataFrame
    - Partitioning by created_utc
    - Upserts based on 'id' column

    Args:
        context: Dagster execution context

    Returns:
        DataFrame with Reddit comment data

    Raises:
        ValueError: If Reddit credentials are not configured
        Exception: If API request fails
    """
    # Configuration - modify these values as needed
    subreddit = "dataengineering"
    time_filter = "day"
    post_limit = 25
    comment_limit = 10

    context.log.info(
        f"Extracting comments from r/{subreddit} "
        f"(posts={post_limit}, comments_per_post={comment_limit})"
    )

    reddit = create_reddit_client()

    comments_data = []
    for post in reddit.subreddit(subreddit).top(time_filter=time_filter, limit=post_limit):
        # Get top comments from this post
        post.comment_sort = "top"
        post.comment_limit = comment_limit
        comments = list(post.comments)[:comment_limit]

        for comment in comments:
            # Skip "MoreComments" objects
            if isinstance(comment, praw.models.MoreComments):
                continue

            comments_data.append({
                # Identity
                "id": comment.id,
                "subreddit": subreddit,
                "created_utc": datetime.fromtimestamp(comment.created_utc),
                "permalink": f"https://reddit.com{comment.permalink}",

                # Threading (for conversation analysis)
                "link_id": post.id,  # Parent post ID
                "parent_id": comment.parent_id,

                # Content
                "body": comment.body,

                # Engagement
                "score": comment.score,
                "controversiality": comment.controversiality,

                # Author
                "author": str(comment.author) if comment.author else "[deleted]",
                "is_submitter": comment.is_submitter,

                # Moderation
                "stickied": comment.stickied,
                "distinguished": comment.distinguished if hasattr(comment, 'distinguished') else None,
            })

    df = pd.DataFrame(comments_data)

    # Convert timestamp to microsecond precision (Iceberg requirement)
    if len(df) > 0:
        df['created_utc'] = pd.to_datetime(df['created_utc']).dt.as_unit('us')

        # Cast integer columns to int32 to match Iceberg schema expectations
        # Pandas defaults to int64 (long), but Iceberg tables use int32 (int)
        if 'score' in df.columns:
            df['score'] = df['score'].astype('int32')
        if 'controversiality' in df.columns:
            df['controversiality'] = df['controversiality'].astype('int32')

    context.log.info(f"Extracted {len(df)} comments from r/{subreddit}")

    # Add metadata to the asset
    if len(df) > 0:
        context.add_output_metadata({
            "num_records": len(df),
            "subreddit": subreddit,
            "num_posts_processed": post_limit,
            "date_range": f"{df['created_utc'].min()} to {df['created_utc'].max()}",
        })
    else:
        context.add_output_metadata({
            "num_records": 0,
            "subreddit": subreddit,
            "num_posts_processed": post_limit,
            "date_range": "No data",
        })

    return df
