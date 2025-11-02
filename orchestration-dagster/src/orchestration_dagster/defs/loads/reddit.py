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
        subreddit: Name of the subreddit (used for naming)

    Returns:
        Configured dlt pipeline for the specified subreddit
    """
    return dlt.pipeline(
        pipeline_name=f"reddit_{subreddit}",
        destination="filesystem",  # Writes Parquet to Garage S3
        dataset_name=f"reddit_{subreddit}",
        progress="log",  # Log progress during execution
        # Note: Iceberg tables will be created in Trino that reference these Parquet files
        # See CLAUDE.md for Iceberg table creation via Trino
    )
