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
from base64 import b64encode
from typing import Any, Iterator, Dict


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
            # Subreddit metadata
            {
                "name": "subreddit",
                "endpoint": {
                    "path": "/about",
                    "data_selector": "data",
                    "paginator": "single_page",  # Explicitly no pagination for metadata
                },
                "write_disposition": "replace",
                "primary_key": "id",
            },
            # Top posts from subreddit
            {
                "name": "posts",
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
                "write_disposition": "append",  # TODO: Enable merge once Trino Iceberg tables created
                "primary_key": "id",
                # NOTE: table_format="iceberg" removed due to Garage S3 checksum compatibility
                # Plan: Write Parquet → Create Iceberg tables in Trino → Enable merge via Trino
            },
            # Top comments from posts
            {
                "name": "comments",
                "endpoint": {
                    "path": "/comments/{resources.posts.id}",
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
                "write_disposition": "append",  # TODO: Enable merge once Trino Iceberg tables created
                "primary_key": "id",
                # NOTE: table_format="iceberg" removed due to Garage S3 checksum compatibility
                # Plan: Write Parquet → Create Iceberg tables in Trino → Enable merge via Trino
            },
        ]
    }

    # Yield REST API resources with add_map transformation for comments
    resources_generator = rest_api_resources(config)

    for resource in resources_generator:
        # Add subreddit field to comments for partitioning support
        if resource.name == "comments":
            def add_subreddit_field(record):
                """Add subreddit field for partition tracking."""
                record["subreddit"] = subreddit
                return record

            resource = resource.add_map(add_subreddit_field)

        yield resource


# Convenience function for common use cases
def load_reddit_data(
    subreddit: str,
    client_id: str = dlt.secrets.value,
    client_secret: str = dlt.secrets.value,
    user_agent: str = dlt.secrets.value,
    time_filter: str = "week",
    limit: int = 100,
    destination: str = "filesystem",
    dataset_name: str = "reddit_data",
) -> Any:
    """
    Load Reddit data directly to a destination.

    Example usage:
        load_reddit_data(
            subreddit="python",
            time_filter="week",
            limit=50,
            destination="duckdb"
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
    load_info = load_reddit_data(
        subreddit="dataengineering",
        time_filter="week",
        limit=25,
        destination="duckdb",
    )
    print(load_info)
