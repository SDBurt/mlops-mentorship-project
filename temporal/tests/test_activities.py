# tests/test_activities.py
"""
Unit tests for Temporal activities.

These tests run the activity logic directly without Temporal,
which is useful for fast unit testing.
"""
import pytest
from unittest.mock import patch, MagicMock

from temporal.activities.fraud_check import check_fraud, FraudCheckResult
from temporal.activities.charge_payments import (
    charge_payment,
    ChargeResult,
    PaymentDeclinedError,
)
from temporal.activities.retry_strategy import get_retry_strategy, RetryStrategy


@pytest.fixture(autouse=True)
def mock_activity_logger():
    """Mock activity.logger for all tests since we're not in an activity context."""
    mock_logger = MagicMock()
    with patch("temporal.activities.fraud_check.activity") as mock_fraud_activity, \
         patch("temporal.activities.charge_payments.activity") as mock_charge_activity, \
         patch("temporal.activities.retry_strategy.activity") as mock_retry_activity:
        mock_fraud_activity.logger = mock_logger
        mock_charge_activity.logger = mock_logger
        mock_retry_activity.logger = mock_logger
        yield mock_logger


class TestFraudCheck:
    """Tests for the fraud check activity."""

    @pytest.fixture
    def sample_payment(self) -> dict:
        """Sample normalized payment data for testing."""
        return {
            "provider": "stripe",
            "provider_payment_id": "pi_test123",
            "amount_cents": 5000,  # $50.00
            "currency": "USD",
            "customer_id": "cus_456",
            "card_brand": "visa",
            "card_last4": "4242",
            "card_funding": "credit",
            "fraud_signals": {
                "cvc_check": "pass",
                "avs_check": "pass",
                "postal_check": "pass",
            },
        }

    @pytest.mark.asyncio
    async def test_fraud_check_returns_result(self, sample_payment):
        """Fraud check should return a FraudCheckResult with risk_level."""
        result = await check_fraud(sample_payment)

        assert isinstance(result, FraudCheckResult)
        assert isinstance(result.is_safe, bool)
        assert 0.0 <= result.risk_score <= 1.0
        assert result.risk_level in ["normal", "elevated", "high"]
        assert isinstance(result.reasons, list)

    @pytest.mark.asyncio
    async def test_high_amount_increases_risk(self, sample_payment):
        """High amounts should increase the risk score."""
        sample_payment["amount_cents"] = 60000  # $600, above $500 threshold

        result = await check_fraud(sample_payment)

        assert "high_amount" in result.reasons

    @pytest.mark.asyncio
    async def test_very_high_amount_flags_both(self, sample_payment):
        """Very high amounts should flag both high and very_high."""
        sample_payment["amount_cents"] = 150000  # $1500, above both thresholds

        result = await check_fraud(sample_payment)

        assert "high_amount" in result.reasons
        assert "very_high_amount" in result.reasons

    @pytest.mark.asyncio
    async def test_unusual_currency_increases_risk(self, sample_payment):
        """Unusual currencies should increase the risk score."""
        sample_payment["currency"] = "jpy"  # Not in safe list

        result = await check_fraud(sample_payment)

        assert "unusual_currency" in result.reasons

    @pytest.mark.asyncio
    async def test_failed_cvc_check_increases_risk(self, sample_payment):
        """Failed CVC check should increase risk."""
        sample_payment["fraud_signals"]["cvc_check"] = "fail"

        result = await check_fraud(sample_payment)

        assert "cvc_check_failed" in result.reasons

    @pytest.mark.asyncio
    async def test_postal_code_mismatch_increases_risk(self, sample_payment):
        """Failed postal code check should increase risk."""
        sample_payment["fraud_signals"]["postal_check"] = "fail"

        result = await check_fraud(sample_payment)

        assert "postal_code_mismatch" in result.reasons

    @pytest.mark.asyncio
    async def test_avs_check_failure_increases_risk(self, sample_payment):
        """Failed AVS check should increase risk."""
        sample_payment["fraud_signals"]["avs_check"] = "fail"

        result = await check_fraud(sample_payment)

        assert "address_mismatch" in result.reasons

    @pytest.mark.asyncio
    async def test_provider_high_risk_increases_score(self, sample_payment):
        """Provider-flagged high risk should add to score."""
        sample_payment["fraud_signals"]["risk_level"] = "high"

        result = await check_fraud(sample_payment)

        assert "provider_flagged_high_risk" in result.reasons

    @pytest.mark.asyncio
    async def test_provider_medium_risk_increases_score(self, sample_payment):
        """Provider-flagged medium risk should add to score."""
        sample_payment["fraud_signals"]["risk_level"] = "medium"

        result = await check_fraud(sample_payment)

        assert "provider_flagged_medium_risk" in result.reasons

    @pytest.mark.asyncio
    async def test_prepaid_card_increases_risk(self, sample_payment):
        """Prepaid cards should increase risk."""
        sample_payment["card_funding"] = "prepaid"

        result = await check_fraud(sample_payment)

        assert "prepaid_card" in result.reasons

    @pytest.mark.asyncio
    async def test_combined_risk_factors(self, sample_payment):
        """Multiple risk factors should accumulate."""
        sample_payment["amount_cents"] = 60000  # High amount
        sample_payment["fraud_signals"]["cvc_check"] = "fail"
        sample_payment["fraud_signals"]["postal_check"] = "fail"

        result = await check_fraud(sample_payment)

        assert "high_amount" in result.reasons
        assert "cvc_check_failed" in result.reasons
        assert "postal_code_mismatch" in result.reasons
        assert result.risk_level in ["elevated", "high"]

    @pytest.mark.asyncio
    async def test_risk_level_thresholds(self, sample_payment):
        """Risk levels should match score thresholds."""
        # Low risk payment should be safe
        result = await check_fraud(sample_payment)

        assert result.risk_level in ["normal", "elevated"]
        assert result.is_safe is True


class TestChargePayment:
    """Tests for the charge payment activity."""

    @pytest.fixture
    def sample_payment(self) -> dict:
        """Sample normalized payment data for testing."""
        return {
            "provider": "stripe",
            "provider_payment_id": "pi_test123",
            "amount_cents": 5000,
            "currency": "USD",
        }

    @pytest.mark.asyncio
    async def test_successful_charge_returns_result(self, sample_payment, monkeypatch):
        """Successful charge should return a ChargeResult."""
        # Mock random to always succeed
        import random
        monkeypatch.setattr(random, "random", lambda: 0.5)  # > 0.15, so no decline
        monkeypatch.setattr(random, "randint", lambda a, b: 1234567)

        result = await charge_payment(sample_payment)

        assert isinstance(result, ChargeResult)
        assert result.status == "succeeded"
        assert result.charge_id == "ch_1234567"
        assert result.amount_charged == 5000

    @pytest.mark.asyncio
    async def test_declined_charge_raises_error(self, sample_payment, monkeypatch):
        """Declined charge should raise PaymentDeclinedError."""
        import random
        monkeypatch.setattr(random, "random", lambda: 0.01)  # < 0.15, so decline
        monkeypatch.setattr(random, "choice", lambda x: "card_declined")

        with pytest.raises(PaymentDeclinedError) as exc_info:
            await charge_payment(sample_payment)

        assert exc_info.value.code == "card_declined"

    @pytest.mark.asyncio
    async def test_charge_uses_normalized_amount_cents(self, sample_payment, monkeypatch):
        """Should use amount_cents from normalized schema."""
        import random
        sample_payment["amount_cents"] = 7500
        monkeypatch.setattr(random, "random", lambda: 0.5)  # No decline
        monkeypatch.setattr(random, "randint", lambda a, b: 1234567)

        result = await charge_payment(sample_payment)

        assert result.amount_charged == 7500

    @pytest.mark.asyncio
    async def test_charge_with_provider_info(self, sample_payment, monkeypatch):
        """Should handle payments with provider information."""
        import random
        sample_payment["provider"] = "square"
        sample_payment["provider_payment_id"] = "sqpay_123"
        monkeypatch.setattr(random, "random", lambda: 0.5)
        monkeypatch.setattr(random, "randint", lambda a, b: 1234567)

        result = await charge_payment(sample_payment)

        assert result.status == "succeeded"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("failure_code", [
        "card_declined",
        "insufficient_funds",
        "expired_card",
        "incorrect_cvc",
        "processing_error",
    ])
    async def test_all_decline_codes(self, sample_payment, failure_code, monkeypatch):
        """All decline codes should raise PaymentDeclinedError with correct code."""
        import random
        monkeypatch.setattr(random, "random", lambda: 0.01)  # Force decline
        monkeypatch.setattr(random, "choice", lambda x: failure_code)

        with pytest.raises(PaymentDeclinedError) as exc_info:
            await charge_payment(sample_payment)

        assert exc_info.value.code == failure_code


class TestRetryStrategy:
    """Tests for the retry strategy activity."""

    @pytest.fixture
    def sample_payment(self) -> dict:
        """Sample payment data for testing."""
        return {
            "transaction_id": "TXN_00000001",
            "amount": 5000,
        }

    @pytest.mark.asyncio
    async def test_card_declined_strategy(self, sample_payment):
        """Card declined should return 24-hour retry strategy."""
        result = await get_retry_strategy(sample_payment, "card_declined", attempt=1)

        assert isinstance(result, RetryStrategy)
        assert result.should_retry is True
        assert result.delay_hours == 24
        assert result.method == "same_card"
        assert result.max_attempts == 3

    @pytest.mark.asyncio
    async def test_expired_card_no_retry(self, sample_payment):
        """Expired card should not retry - needs customer action."""
        # Note: expired_card has max_attempts=0, so any attempt triggers give_up
        result = await get_retry_strategy(sample_payment, "expired_card", attempt=1)

        assert result.should_retry is False
        assert result.method == "give_up"  # Falls through to give_up since attempt >= max_attempts(0)

    @pytest.mark.asyncio
    async def test_max_attempts_reached(self, sample_payment):
        """Should give up when max attempts reached."""
        result = await get_retry_strategy(sample_payment, "card_declined", attempt=5)

        assert result.should_retry is False
        assert result.method == "give_up"

    @pytest.mark.asyncio
    async def test_unknown_failure_code_default_strategy(self, sample_payment):
        """Unknown failure codes should get default strategy."""
        result = await get_retry_strategy(sample_payment, "unknown_error", attempt=1)

        assert result.should_retry is True
        assert result.delay_hours == 24
        assert result.method == "same_card"

    @pytest.mark.asyncio
    async def test_insufficient_funds_strategy(self, sample_payment):
        """Insufficient funds should have 48-hour delay, 5 attempts."""
        result = await get_retry_strategy(sample_payment, "insufficient_funds", attempt=1)

        assert result.should_retry is True
        assert result.delay_hours == 48
        assert result.method == "same_card"
        assert result.max_attempts == 5

    @pytest.mark.asyncio
    async def test_incorrect_cvc_strategy(self, sample_payment):
        """Incorrect CVC should have 1-hour delay, 2 attempts."""
        result = await get_retry_strategy(sample_payment, "incorrect_cvc", attempt=1)

        assert result.should_retry is True
        assert result.delay_hours == 1
        assert result.method == "same_card"
        assert result.max_attempts == 2

    @pytest.mark.asyncio
    async def test_processing_error_strategy(self, sample_payment):
        """Processing error should have 6-hour delay, 3 attempts."""
        result = await get_retry_strategy(sample_payment, "processing_error", attempt=1)

        assert result.should_retry is True
        assert result.delay_hours == 6
        assert result.method == "same_card"
        assert result.max_attempts == 3

    @pytest.mark.asyncio
    async def test_insufficient_funds_max_attempts(self, sample_payment):
        """Should give up after 5 attempts for insufficient_funds."""
        result = await get_retry_strategy(sample_payment, "insufficient_funds", attempt=5)

        assert result.should_retry is False
        assert result.method == "give_up"
