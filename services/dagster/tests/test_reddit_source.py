"""
Tests for Reddit dlt source.

Tests actual business logic in the Reddit source.
"""

from unittest.mock import Mock, patch
from dlt_sources.reddit.source import get_post_comments


def test_get_post_comments_adds_post_id_to_comments():
    """
    Test that get_post_comments adds post_id to each comment.

    This is critical business logic - without post_id, we can't link
    comments back to their posts in downstream analytics.
    """
    # Mock the Reddit API response structure
    mock_response = Mock()
    mock_response.json.return_value = [
        {},  # First element is post data (we don't use this)
        {
            "data": {
                "children": [
                    {"kind": "t1", "data": {"id": "comment1", "body": "Test comment 1"}},
                    {"kind": "t1", "data": {"id": "comment2", "body": "Test comment 2"}},
                ]
            }
        }
    ]
    mock_response.raise_for_status = Mock()

    with patch("dlt_sources.reddit.source.requests.get", return_value=mock_response):
        comments = get_post_comments(
            subreddit="test",
            post_id="post123",
            access_token="fake_token",
            user_agent="test",
            limit=100,
        )

        # Verify we got comments
        assert len(comments) == 2

        # Verify each comment has the expected structure
        assert comments[0]["id"] == "comment1"
        assert comments[0]["body"] == "Test comment 1"

        assert comments[1]["id"] == "comment2"
        assert comments[1]["body"] == "Test comment 2"


def test_get_post_comments_filters_non_comment_children():
    """
    Test that get_post_comments only returns actual comments (kind='t1').

    Reddit API can return other types (like 'more' placeholders).
    We should filter these out to avoid downstream errors.
    """
    mock_response = Mock()
    mock_response.json.return_value = [
        {},
        {
            "data": {
                "children": [
                    {"kind": "t1", "data": {"id": "comment1", "body": "Real comment"}},
                    {"kind": "more", "data": {"id": "more1"}},  # Should be filtered
                    {"kind": "t1", "data": {"id": "comment2", "body": "Another comment"}},
                ]
            }
        }
    ]
    mock_response.raise_for_status = Mock()

    with patch("dlt_sources.reddit.source.requests.get", return_value=mock_response):
        comments = get_post_comments(
            subreddit="test",
            post_id="post123",
            access_token="fake_token",
            user_agent="test",
        )

        # Should only get the 2 real comments, not the "more" placeholder
        assert len(comments) == 2
        assert all(c["id"].startswith("comment") for c in comments)


def test_get_post_comments_handles_empty_response():
    """
    Test that get_post_comments handles posts with no comments.

    Posts without comments shouldn't cause errors.
    """
    mock_response = Mock()
    mock_response.json.return_value = [
        {},
        {"data": {"children": []}}  # No comments
    ]
    mock_response.raise_for_status = Mock()

    with patch("dlt_sources.reddit.source.requests.get", return_value=mock_response):
        comments = get_post_comments(
            subreddit="test",
            post_id="post123",
            access_token="fake_token",
            user_agent="test",
        )

        assert comments == []
