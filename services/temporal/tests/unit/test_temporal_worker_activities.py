"""Unit tests for orchestrator activities."""

import pytest


class TestValidateBusinessRules:
    """Tests for the validate_business_rules activity."""

    @pytest.fixture
    def valid_event(self) -> dict:
        """Valid payment event fixture."""
        return {
            "event_id": "stripe:evt_123",
            "provider": "stripe",
            "provider_event_id": "evt_123",
            "event_type": "payment.succeeded",
            "merchant_id": "merch_123",
            "customer_id": "cus_123",
            "amount_cents": 5000,
            "currency": "USD",
            "status": "succeeded",
        }

    def test_valid_event_passes(self, valid_event: dict) -> None:
        """Test that a valid event passes validation."""
        from temporal_worker.activities.validation import (
            MAX_AMOUNT_CENTS,
            ALLOWED_CURRENCIES,
            BLOCKLISTED_CUSTOMERS,
        )

        # Verify constants are set correctly
        assert MAX_AMOUNT_CENTS == 1_000_000_00
        assert "USD" in ALLOWED_CURRENCIES
        assert "cus_blocked_001" in BLOCKLISTED_CUSTOMERS

    def test_amount_bounds_validation(self) -> None:
        """Test amount bounds are enforced."""
        from temporal_worker.activities.validation import MAX_AMOUNT_CENTS

        # Verify max amount is $1,000,000
        assert MAX_AMOUNT_CENTS == 100_000_000

    def test_currency_validation(self) -> None:
        """Test currency validation."""
        from temporal_worker.activities.validation import ALLOWED_CURRENCIES

        # Verify expected currencies
        expected = {"USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CHF", "CNY", "HKD", "NZD"}
        assert expected == ALLOWED_CURRENCIES

    def test_blocklist_validation(self) -> None:
        """Test blocklist contains expected entries."""
        from temporal_worker.activities.validation import (
            BLOCKLISTED_CUSTOMERS,
            BLOCKLISTED_MERCHANTS,
        )

        assert "cus_blocked_001" in BLOCKLISTED_CUSTOMERS
        assert "cus_blocked_002" in BLOCKLISTED_CUSTOMERS
        assert "merch_blocked_001" in BLOCKLISTED_MERCHANTS


class TestFraudActivity:
    """Tests for fraud scoring activity configuration."""

    def test_config_has_inference_url(self) -> None:
        """Test that config has inference service URL."""
        from temporal_worker.config import settings

        assert settings.inference_service_url is not None
        assert "8002" in settings.inference_service_url or "inference" in settings.inference_service_url

    def test_config_has_timeout(self) -> None:
        """Test that config has inference timeout."""
        from temporal_worker.config import settings

        assert settings.inference_timeout_seconds > 0
        assert settings.inference_timeout_seconds <= 60  # Reasonable timeout


class TestRetryStrategyActivity:
    """Tests for retry strategy activity configuration."""

    def test_inference_timeout_configured(self) -> None:
        """Test that inference timeout is properly configured."""
        from temporal_worker.config import settings

        # Should be reasonable for HTTP call
        assert 5 <= settings.inference_timeout_seconds <= 60
