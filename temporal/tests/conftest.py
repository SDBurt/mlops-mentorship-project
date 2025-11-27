# tests/conftest.py
"""
Pytest configuration and fixtures for Temporal workflow tests.
"""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def reset_kafka_producer():
    """Reset the global Kafka producer between tests."""
    from temporal.activities import kafka_emitter
    kafka_emitter._producer_wrapper = None
    yield
    kafka_emitter._producer_wrapper = None


@pytest.fixture
def mock_activity_logger():
    """
    Provide mocked activity.logger for unit tests that call activities directly.

    Use this fixture explicitly in tests that need to call activity functions
    outside of a Temporal worker context.
    """
    mock_logger = MagicMock()

    # Import actual modules (not the exported functions)
    import temporal.activities.validate_event as validate_event_mod
    import temporal.activities.normalize_event as normalize_event_mod
    import temporal.activities.enrich_context as enrich_context_mod
    import temporal.activities.predict_retry_strategy as predict_mod
    import temporal.activities.provider_retry as retry_mod
    import temporal.activities.kafka_emitter as kafka_mod

    # Patch the activity.logger in each module
    patches = []
    modules = [
        validate_event_mod,
        normalize_event_mod,
        enrich_context_mod,
        predict_mod,
        retry_mod,
        kafka_mod,
    ]

    for mod in modules:
        if hasattr(mod, "activity"):
            p = patch.object(mod.activity, "logger", mock_logger)
            patches.append(p)

    for p in patches:
        p.start()

    yield mock_logger

    for p in patches:
        p.stop()
