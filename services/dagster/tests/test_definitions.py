"""
Tests for Dagster definitions.

Tests critical configuration that could break functionality if misconfigured.
"""

from dagster import DefaultScheduleStatus
from orchestration_dagster.definitions import defs, reddit_hourly_schedule


def test_hourly_schedule_configuration():
    """
    Test that the hourly schedule is configured correctly.

    This is critical because:
    - If the schedule isn't auto-enabled, data won't be collected
    - If the cron is wrong, data collection timing will be off
    - If it targets the wrong job, we'll collect duplicate subreddit metadata
    """
    schedule = reddit_hourly_schedule

    # Schedule should be enabled by default (auto-start data collection)
    assert schedule.default_status == DefaultScheduleStatus.RUNNING, \
        "Schedule should be auto-enabled to start collecting data immediately"

    # Schedule should run hourly to capture fresh content
    assert schedule.cron_schedule == "0 * * * *", \
        "Schedule should run every hour at minute 0"

    # Schedule should target posts/comments job, NOT the full job (which includes subreddit)
    assert schedule.job.name == "reddit_posts_comments_job", \
        "Schedule should target posts/comments job to avoid redundant subreddit fetches"


def test_definitions_can_be_loaded():
    """
    Test that definitions load without errors.

    This catches syntax errors, import issues, or circular dependencies.
    """
    assert defs is not None
    assert len(list(defs.assets)) > 0
    assert len(list(defs.jobs)) > 0
    assert len(list(defs.schedules)) > 0
