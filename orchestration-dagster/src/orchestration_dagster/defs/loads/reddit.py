"""
Dagster dlt pipeline for Reddit data ingestion.

This module defines factory functions for creating dlt sources and pipelines
dynamically for different subreddits (used with Dagster partitions).
"""

import dlt
from dlt_sources.reddit.source import reddit_source


def create_reddit_source(subreddit: str):
    """
    Factory function to create reddit source for a specific subreddit.

    Args:
        subreddit: Name of the subreddit to extract data from

    Returns:
        Configured dlt source for the specified subreddit
    """
    return reddit_source(
        subreddit=subreddit,
        time_filter="day",  # Get top posts from today
        limit=10,  # Max posts/comments per request
    )


def create_reddit_pipeline(subreddit: str):
    """
    Factory function to create reddit pipeline for a specific subreddit.

    Args:
        subreddit: Name of the subreddit (used for naming and filtering)

    Returns:
        Configured dlt pipeline for the specified subreddit
    """
    return dlt.pipeline(
        pipeline_name=f"reddit_{subreddit}",
        destination="filesystem",  # Use filesystem destination with table_format="iceberg" on resources
        dataset_name=f"raw_{subreddit}",  # Separate dataset per subreddit (namespace in Polaris via PyIceberg config)
        progress="log",  # Log progress during execution
        # Creates Iceberg tables via PyIceberg → Polaris REST catalog:
        # - lakehouse.raw_economics.reddit_economics_posts
        # - lakehouse.raw_economics.reddit_economics_comments
        # - lakehouse.raw_economics.reddit_economics_subreddit
        # Polaris manages metadata, MinIO stores data: s3://lakehouse/iceberg/raw_economics/reddit_economics_posts/
        # DBT will union across namespaces: raw_*.reddit_*_posts → staging.stg_reddit_posts → marts.fct_posts
    )
