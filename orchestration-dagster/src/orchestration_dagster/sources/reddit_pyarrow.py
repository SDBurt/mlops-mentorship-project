"""
Reddit data source using PRAW with PyArrow backend.

This is an alternative to reddit.py that uses PyArrow tables instead of Pandas DataFrames.
PyArrow provides better performance and memory efficiency for larger datasets.

Usage:
    Use this instead of reddit.py when:
    - Working with large datasets (>100k rows)
    - Memory is constrained
    - Performance is critical
    - Need columnar data format

    Use reddit.py (Pandas) when:
    - Working with small-to-medium datasets
    - Need familiar DataFrame API
    - Interactive data exploration
"""

import praw
import pyarrow as pa
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
    key_prefix=["raw", "reddit"],
    io_manager_key="iceberg_io_manager",
    metadata={
        "partition_expr": "created_utc",  # Iceberg partition column
    },
    group_name="reddit_ingestion_pyarrow",
    compute_kind="api",
)
def reddit_posts_pyarrow(context: AssetExecutionContext) -> pa.Table:
    """
    Extract Reddit posts using PRAW and return as PyArrow table.

    The dagster-iceberg IO manager automatically handles:
    - Table creation (lakehouse.raw.reddit_posts_pyarrow)
    - Schema inference from PyArrow Table
    - Partitioning by created_utc
    - Upserts based on 'id' column

    Args:
        context: Dagster asset execution context

    Returns:
        PyArrow Table with Reddit post data

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

    # Convert to PyArrow Table (more efficient than DataFrame for large data)
    table = pa.Table.from_pylist(posts_data)

    context.log.info(f"Extracted {len(table)} posts from r/{subreddit}")

    # Add metadata to the asset
    if len(table) > 0:
        # Get min/max dates from the table
        created_utc_col = table.column("created_utc")
        min_date = created_utc_col.to_pylist()[0]
        max_date = created_utc_col.to_pylist()[-1]

        context.add_output_metadata({
            "num_records": len(table),
            "subreddit": subreddit,
            "time_filter": time_filter,
            "date_range": f"{min_date} to {max_date}",
            "schema": str(table.schema),
            "size_bytes": table.nbytes,
        })
    else:
        context.add_output_metadata({
            "num_records": 0,
            "subreddit": subreddit,
            "time_filter": time_filter,
            "date_range": "No data",
        })

    return table


@asset(
    key_prefix=["raw", "reddit"],
    io_manager_key="iceberg_io_manager",
    metadata={
        "partition_expr": "created_utc",  # Iceberg partition column
    },
    deps=[reddit_posts_pyarrow],  # Depends on posts asset
    group_name="reddit_ingestion_pyarrow",
    compute_kind="api",
)
def reddit_comments_pyarrow(context: AssetExecutionContext) -> pa.Table:
    """
    Extract Reddit comments from top posts using PRAW.

    The dagster-iceberg IO manager automatically handles:
    - Table creation (lakehouse.raw.reddit_comments_pyarrow)
    - Schema inference from PyArrow Table
    - Partitioning by created_utc
    - Upserts based on 'id' column

    Args:
        context: Dagster execution context

    Returns:
        PyArrow Table with Reddit comment data

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

    # Convert to PyArrow Table
    table = pa.Table.from_pylist(comments_data)

    context.log.info(f"Extracted {len(table)} comments from r/{subreddit}")

    # Add metadata to the asset
    if len(table) > 0:
        created_utc_col = table.column("created_utc")
        min_date = created_utc_col.to_pylist()[0]
        max_date = created_utc_col.to_pylist()[-1]

        context.add_output_metadata({
            "num_records": len(table),
            "subreddit": subreddit,
            "num_posts_processed": post_limit,
            "date_range": f"{min_date} to {max_date}",
            "schema": str(table.schema),
            "size_bytes": table.nbytes,
        })
    else:
        context.add_output_metadata({
            "num_records": 0,
            "subreddit": subreddit,
            "num_posts_processed": post_limit,
            "date_range": "No data",
        })

    return table
