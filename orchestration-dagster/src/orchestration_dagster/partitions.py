"""
Dagster partition definitions for orchestration.

This module defines static partitions for different data sources,
enabling parallel processing and selective backfills.
"""

from dagster import StaticPartitionsDefinition


# Define subreddits to track
# Add or remove subreddits here to update the partition set
# Current focus: World news, economics, and finance
SUBREDDITS = [
    "worldnews",
    "economics",
    "finance",
    "wallstreetbets",
    "investing",
]

# Static partition definition for subreddit-based processing
# Each subreddit will be processed independently
subreddit_partitions = StaticPartitionsDefinition(SUBREDDITS)
