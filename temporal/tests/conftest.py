# tests/conftest.py
"""
Pytest configuration and fixtures for Temporal workflow tests.
"""
import pytest


@pytest.fixture(autouse=True)
def reset_kafka_producer():
    """Reset the global Kafka producer between tests."""
    from temporal.activities import kafka_emitter
    kafka_emitter._producer_wrapper = None
    yield
    kafka_emitter._producer_wrapper = None
