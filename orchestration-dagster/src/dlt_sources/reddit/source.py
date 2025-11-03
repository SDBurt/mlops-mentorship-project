"""
Reddit dlt REST API source for extracting subreddit data, top posts, and comments.

This source uses Reddit's OAuth2 API with client credentials grant for read-only access
to public subreddit data. It extracts:
- Subreddit metadata
- Top posts from subreddits
- Top comments from posts

Configuration via .dlt/secrets.toml:
    [sources.source.reddit]
    client_id = "your_client_id"
    client_secret = "your_client_secret"
    user_agent = "python:lakehouse-dlt:v1.0.0 (by /u/your_username)"

Reddit API documentation: https://www.reddit.com/dev/api
"""

import dlt
from dlt.sources.rest_api import rest_api_resources
from dlt.sources.helpers.rest_client.auth import OAuth2ClientCredentials
from dlt.common.configuration import configspec
import json
import logging
from base64 import b64encode
from typing import Any, Iterator, Dict

logger = logging.getLogger(__name__)


# ============================================================================
# FIELD DEFINITIONS - Explicit schema control for ML feature engineering
# ============================================================================

POSTS_FIELDS = [
    # Identity
    'id', 'name', 'subreddit', 'created_utc', 'permalink',
    # Content
    'title', 'selftext', 'url', 'domain',
    # Engagement metrics
    'score', 'upvote_ratio', 'num_comments', 'num_crossposts',
    # Awards (aggregate counts)
    'total_awards_received', 'gilded',
    # User interaction signals
    'clicked', 'visited', 'saved', 'hidden',
    # Author features
    'author', 'author_fullname', 'author_premium', 'author_flair_text',
    # Content type classification
    'is_self', 'is_video', 'is_gallery', 'post_hint', 'over_18',
    # Moderation/quality
    'stickied', 'locked', 'archived', 'edited',
]

COMMENTS_FIELDS = [
    # Identity
    'id', 'name', 'subreddit', 'created_utc', 'permalink',
    # Threading (for joins and conversation analysis)
    'link_id', 'parent_id', 'depth',
    # Content
    'body',
    # Engagement metrics
    'score', 'ups', 'downs', 'controversiality',
    # Awards (aggregate counts)
    'total_awards_received', 'gilded',
    # Author features
    'author', 'author_fullname', 'author_premium', 'author_flair_text', 'is_submitter',
    # Moderation/quality
    'stickied', 'distinguished', 'score_hidden', 'edited',
]

# Complex nested fields to store as JSON strings
COMPLEX_FIELDS = ['gildings', 'all_awardings']


def select_and_transform_fields(record, field_list):
    """
    Extract only specified fields from Reddit API response.

    This solves schema evolution issues by ensuring:
    1. Consistent field set across all subreddits
    2. Same field order every time
    3. Missing optional fields become NULL (not schema errors)
    4. Complex nested objects stringified as JSON

    Args:
        record: Raw Reddit API record (dict)
        field_list: List of field names to extract

    Returns:
        Dict with only selected fields, or None if record is None
    """
    if record is None:
        return None

    # Extract only specified fields
    selected = {}
    for field in field_list:
        if field in record:
            selected[field] = record[field]
        # Missing fields will be NULL in Iceberg (not an error)

    # Stringify complex nested objects (awards, media metadata)
    # These can be unnested/parsed in downstream processing
    for complex_field in COMPLEX_FIELDS:
        if complex_field in record and record[complex_field]:
            selected[complex_field] = json.dumps(record[complex_field])

    return selected


@configspec
class RedditOAuth2ClientCredentials(OAuth2ClientCredentials):
    """
    OAuth2 authentication for Reddit API with HTTP Basic Auth and User-Agent.

    Reddit requires:
    - HTTP Basic Auth with Base64 encoded client_id:client_secret
    - User-Agent header (Reddit rejects generic user agents)
    - grant_type=client_credentials

    This class integrates with dlt's configuration system and enables
    automatic token refresh using the @configspec decorator.

    Example:
        auth = RedditOAuth2ClientCredentials(
            access_token_url="https://www.reddit.com/api/v1/access_token",
            client_id=dlt.secrets["sources.reddit.client_id"],
            client_secret=dlt.secrets["sources.reddit.client_secret"],
            user_agent=dlt.secrets["sources.reddit.user_agent"],
            access_token_request_data={"grant_type": "client_credentials"},
        )
    """

    user_agent: str = "dlt:reddit:v1.0"  # Additional field for Reddit's User-Agent requirement

    def build_access_token_request(self) -> Dict[str, Any]:
        """
        Build token request with HTTP Basic Auth and User-Agent header.

        Reddit's OAuth2 endpoint expects HTTP Basic Auth (not Bearer) for
        the token request, plus a custom User-Agent header.

        Returns:
            Request configuration dict with headers and data for token endpoint
        """
        # Encode credentials for HTTP Basic Auth header
        authentication: str = b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        return {
            "headers": {
                "Authorization": f"Basic {authentication}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": self.user_agent,  # Required by Reddit
            },
            "data": self.access_token_request_data,
        }


def transform_reddit_comments_response(response, *args, **kwargs):
    data = response.json()

    # Extract comments from second element of array
    if len(data) > 1 and "data" in data[1]:
        comments_listing = data[1]

        # Filter only comment objects (kind == "t1"), exclude "more" placeholders
        children = comments_listing["data"].get("children", [])
        filtered_children = [
            child for child in children
            if child.get("kind") == "t1"
        ]

        # Reconstruct as standard listing format for data_selector
        transformed = {
            "kind": "Listing",
            "data": {
                "children": filtered_children,
                "after": comments_listing["data"].get("after"),
                "before": comments_listing["data"].get("before")
            }
        }

        # Update response content
        response._content = json.dumps(transformed).encode("utf-8")

    return response


@dlt.source(name="reddit", max_table_nesting=0)
def reddit_source(
    subreddit: str,
    client_id: str = dlt.secrets.value,
    client_secret: str = dlt.secrets.value,
    user_agent: str = dlt.secrets.value,
    time_filter: str = dlt.config.value,  # all, year, month, week, day, hour
    limit: int = dlt.config.value
) -> Iterator[Any]:
    """
    Extracts data from Reddit's API for a specific subreddit.

    Args:
        subreddit: Name of the subreddit to extract data from (e.g., "python")
        client_id: Reddit API client ID
        client_secret: Reddit API client secret
        user_agent: User-Agent string (format: platform:app_id:version (by /u/username))
        time_filter: Time filter for top posts (all, year, month, week, day, hour)
        limit: Maximum number of posts/comments to retrieve per request

    Yields:
        dlt resources for subreddit, posts, and comments
    """

    # Create Reddit OAuth2 authentication with automatic token refresh
    # The @configspec decorator enables dlt's configuration management
    # Note: user_agent comes from dlt.secrets.value (line 113), ensuring it's
    # loaded from environment/secrets and not hardcoded
    auth = RedditOAuth2ClientCredentials(
        access_token_url="https://www.reddit.com/api/v1/access_token",
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,  # Populated from secrets via function parameter
        access_token_request_data={
            "grant_type": "client_credentials"
        },
    )

    # Configure REST API source with Reddit OAuth2 authentication
    config = {
        "client": {
            "base_url": f"https://oauth.reddit.com/r/{subreddit}",
            "auth": auth,  # Pass OAuth2 instance directly - enables auto token refresh
            "headers": {
                "User-Agent": user_agent,  # Also needed for API requests
            },
        },
        "resources": [
            # Subreddit metadata - separate table per subreddit
            {
                "name": f"reddit_{subreddit}_subreddit",  # Table name includes subreddit
                "endpoint": {
                    "path": "/about",
                    "data_selector": "data",
                    "paginator": "single_page",  # Explicitly no pagination for metadata
                },
                "write_disposition": "replace",
                "primary_key": "id",
            },
            # Top posts from subreddit - separate table per subreddit
            {
                "name": f"reddit_{subreddit}_posts",  # Table name includes subreddit
                "endpoint": {
                    "path": "/top",
                    "params": {
                        "t": time_filter,
                        "limit": limit,
                    },
                    "data_selector": "data.children[*].data",
                    "paginator": {
                        "type": "cursor",
                        "cursor_path": "data.after",
                        "cursor_param": "after",
                    },
                },
                "write_disposition": {
                    "disposition": "merge",
                    "strategy": "upsert"
                },
                "primary_key": "id",
                "table_format": "iceberg",  # Write to Iceberg tables via PyIceberg → Polaris REST catalog
                "columns": {
                    "created_utc": {"partition": True},  # Partition by time for time-series queries
                }
            },
            # Top comments from posts - separate table per subreddit
            {
                "name": f"reddit_{subreddit}_comments",  # Table name includes subreddit
                "endpoint": {
                    "path": "/comments/{resources.reddit_" + subreddit + "_posts.id}",  # Reference posts table for this subreddit
                    "params": {
                        "limit": limit,
                        "sort": "top",
                    },
                    "data_selector": "data.children[*].data",
                    "paginator": "single_page",  # Explicitly no pagination - fetches top N comments per post
                    "response_actions": [
                        transform_reddit_comments_response
                    ],
                },
                "include_from_parent": ["id"],
                "write_disposition": {
                    "disposition": "merge",
                    "strategy": "upsert"
                },
                "primary_key": "id",
                "table_format": "iceberg",  # Write to Iceberg tables via PyIceberg → Polaris REST catalog
                "columns": {
                    "created_utc": {"partition": True},  # Partition by time for time-series queries
                }
            },
        ]
    }

    # Yield REST API resources with transformations
    resources_generator = rest_api_resources(config)

    for resource in resources_generator:
        # Apply field selection to posts and comments with client-side deduplication
        # Note: Client-side deduplication is REQUIRED to handle Reddit API pagination overlap
        # (new posts push old posts into subsequent pages, causing duplicates)
        # PyIceberg rejects batches with internal duplicates even with upsert strategy
        # Each subreddit gets its own tables, so no concurrent write conflicts
        if resource.name == f"reddit_{subreddit}_posts":
            # Track seen IDs for this resource (closure maintains state across records)
            seen_post_ids = set()

            def transform_posts(record):
                """
                Transform with client-side deduplication: select ML-relevant fields and add subreddit.

                Deviates from pure stateless pattern to handle Reddit API behavior:
                - Reddit API returns duplicate IDs when paginating through dynamic datasets
                - New posts push old posts into subsequent pages (expected behavior)
                - PyIceberg requires no internal duplicates in batch (even with upsert)
                - Keeps first occurrence to preserve pagination order

                Per Reddit best practices: "Implement robust client-side deduplication"
                https://www.reddit.com/dev/api
                """
                # Select only ML-relevant fields (solves schema evolution)
                transformed = select_and_transform_fields(record, POSTS_FIELDS)

                if transformed:
                    post_id = transformed.get('id')

                    # Check for duplicates (Reddit API pagination overlap)
                    if post_id in seen_post_ids:
                        logger.info(f"[{subreddit}] Duplicate post ID removed: {post_id}")
                        return None

                    # Track this ID and add subreddit field
                    seen_post_ids.add(post_id)
                    transformed["subreddit"] = subreddit

                return transformed

            # Apply transformation and filter out None records
            resource = resource.add_map(transform_posts).add_filter(lambda x: x is not None)

        elif resource.name == f"reddit_{subreddit}_comments":
            # Track seen IDs for this resource (closure maintains state across records)
            seen_comment_ids = set()

            def transform_comments(record):
                """
                Transform with client-side deduplication: select ML-relevant fields and add subreddit.

                Deviates from pure stateless pattern to handle Reddit API behavior:
                - Reddit API can return duplicate comments (pagination, concurrent requests)
                - Duplicate posts result in duplicate comment fetches (via include_from_parent)
                - PyIceberg requires no internal duplicates in batch (even with upsert)
                - Keeps first occurrence to preserve order

                Per Reddit best practices: "Implement robust client-side deduplication"
                https://www.reddit.com/dev/api
                """
                # Select only ML-relevant fields (solves schema evolution)
                transformed = select_and_transform_fields(record, COMMENTS_FIELDS)

                if transformed:
                    comment_id = transformed.get('id')

                    # Check for duplicates (Reddit API behavior + post duplicates)
                    if comment_id in seen_comment_ids:
                        logger.info(f"[{subreddit}] Duplicate comment ID removed: {comment_id}")
                        return None

                    # Track this ID and add subreddit field
                    seen_comment_ids.add(comment_id)
                    transformed["subreddit"] = subreddit

                return transformed

            # Apply transformation and filter out None records
            resource = resource.add_map(transform_comments).add_filter(lambda x: x is not None)

        yield resource


# Convenience function for common use cases
def load_reddit_data(
    subreddit: str,
    client_id: str = dlt.secrets.value,
    client_secret: str = dlt.secrets.value,
    user_agent: str = dlt.secrets.value,
    time_filter: str = "week",
    limit: int = 100,
    destination: str = "filesystem",  # Use filesystem with table_format="iceberg"
    dataset_name: str = "raw",  # DLT ingestion layer (DBT reads from raw.*)
) -> Any:
    """
    Load Reddit data directly to a destination.

    Example usage:
        load_reddit_data(
            subreddit="python",
            time_filter="week",
            limit=50,
            destination="filesystem"  # Creates Iceberg tables: raw.reddit_posts, raw.reddit_comments
        )
    """
    pipeline = dlt.pipeline(
        pipeline_name="reddit_pipeline",
        destination=destination,
        dataset_name=dataset_name,
    )

    load_info = pipeline.run(
        reddit_source(
            subreddit=subreddit,
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            time_filter=time_filter,
            limit=limit,
        )
    )

    return load_info


if __name__ == "__main__":
    # Example usage when running as script
    # Note: Requires .dlt/secrets.toml with Reddit and MinIO credentials
    load_info = load_reddit_data(
        subreddit="dataengineering",
        time_filter="week",
        limit=25,
        destination="filesystem",  # Creates Iceberg tables via table_format="iceberg"
    )
    print(load_info)
