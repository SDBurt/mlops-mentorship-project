"""
Tests for Dagster schedule execution.

Tests schedule tick generation to ensure automation works correctly.
"""

from dagster import build_schedule_context
from orchestration_dagster.definitions import reddit_hourly_schedule


def test_schedule_generates_run_request():
    """
    Test that the schedule generates a valid run request.

    This is important because if the schedule can't generate run requests,
    the hourly automation won't work even if the schedule is enabled.
    """
    context = build_schedule_context()
    run_request = reddit_hourly_schedule.evaluate_tick(context)

    assert run_request is not None, \
        "Schedule should generate a run request for hourly execution"
