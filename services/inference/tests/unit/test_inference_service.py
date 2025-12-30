"""Unit tests for inference service."""

import pytest


class TestFraudScoring:
    """Tests for fraud scoring logic."""

    def test_compute_fraud_score_low_amount(self) -> None:
        """Test fraud scoring for low amount transactions."""
        from inference_service.routes.fraud import (
            compute_fraud_score_mock,
            FraudScoreRequest,
        )

        request = FraudScoreRequest(
            event_id="stripe:evt_123",
            amount_cents=1000,  # $10
            currency="USD",
            customer_id="cus_123",
            payment_method_type="card",
            card_brand="visa",
        )

        score, factors = compute_fraud_score_mock(request)

        # Low amount with known customer should have low score
        assert 0.0 <= score <= 1.0
        assert "very_high_amount" not in factors
        assert "guest_checkout" not in factors

    def test_compute_fraud_score_high_amount(self) -> None:
        """Test fraud scoring for high amount transactions."""
        from inference_service.routes.fraud import (
            compute_fraud_score_mock,
            FraudScoreRequest,
        )

        request = FraudScoreRequest(
            event_id="stripe:evt_456",
            amount_cents=150_000_00,  # $1500
            currency="USD",
            customer_id="cus_456",
            payment_method_type="card",
        )

        score, factors = compute_fraud_score_mock(request)

        assert 0.0 <= score <= 1.0
        assert "very_high_amount" in factors

    def test_compute_fraud_score_guest_checkout(self) -> None:
        """Test fraud scoring for guest checkout (no customer ID)."""
        from inference_service.routes.fraud import (
            compute_fraud_score_mock,
            FraudScoreRequest,
        )

        request = FraudScoreRequest(
            event_id="stripe:evt_789",
            amount_cents=5000,
            currency="USD",
            customer_id=None,  # Guest checkout
            payment_method_type="card",
        )

        score, factors = compute_fraud_score_mock(request)

        assert 0.0 <= score <= 1.0
        assert "guest_checkout" in factors

    def test_risk_level_thresholds(self) -> None:
        """Test risk level classification."""
        from inference_service.routes.fraud import get_risk_level

        assert get_risk_level(0.1) == "low"
        assert get_risk_level(0.29) == "low"
        assert get_risk_level(0.3) == "medium"
        assert get_risk_level(0.5) == "medium"
        assert get_risk_level(0.7) == "high"
        assert get_risk_level(0.9) == "high"


class TestRetryStrategy:
    """Tests for retry strategy logic."""

    def test_non_retryable_codes(self) -> None:
        """Test that non-retryable codes are handled correctly."""
        from inference_service.routes.retry import (
            compute_retry_strategy,
            RetryStrategyRequest,
            RetryAction,
        )

        for code in ["card_declined", "fraudulent", "stolen_card"]:
            request = RetryStrategyRequest(
                event_id="stripe:evt_fail",
                failure_code=code,
                amount_cents=5000,
                attempt_count=1,
            )

            action, delay, confidence, reason = compute_retry_strategy(request)

            assert action == RetryAction.DO_NOT_RETRY
            assert delay is None
            assert confidence >= 0.9
            assert code in reason.lower()

    def test_customer_action_codes(self) -> None:
        """Test that customer action codes are handled correctly."""
        from inference_service.routes.retry import (
            compute_retry_strategy,
            RetryStrategyRequest,
            RetryAction,
        )

        request = RetryStrategyRequest(
            event_id="stripe:evt_fail",
            failure_code="insufficient_funds",
            amount_cents=5000,
            attempt_count=1,
        )

        action, delay, confidence, reason = compute_retry_strategy(request)

        assert action == RetryAction.CONTACT_CUSTOMER
        assert delay is None

    def test_transient_failure_retry(self) -> None:
        """Test that transient failures get retry recommendation."""
        from inference_service.routes.retry import (
            compute_retry_strategy,
            RetryStrategyRequest,
            RetryAction,
        )

        request = RetryStrategyRequest(
            event_id="stripe:evt_fail",
            failure_code="processing_error",
            amount_cents=5000,
            attempt_count=1,
        )

        action, delay, confidence, reason = compute_retry_strategy(request)

        assert action == RetryAction.RETRY_DELAYED
        assert delay is not None
        assert delay > 0

    def test_exponential_backoff(self) -> None:
        """Test that retry delays increase with attempt count."""
        from inference_service.routes.retry import (
            compute_retry_strategy,
            RetryStrategyRequest,
        )

        delays = []
        for attempt in range(1, 4):
            request = RetryStrategyRequest(
                event_id="stripe:evt_fail",
                failure_code="try_again_later",
                amount_cents=5000,
                attempt_count=attempt,
            )
            _, delay, _, _ = compute_retry_strategy(request)
            delays.append(delay)

        # Verify exponential backoff
        assert delays[1] > delays[0]
        assert delays[2] > delays[1]

    def test_max_attempts_reached(self) -> None:
        """Test that max attempts are enforced."""
        from inference_service.routes.retry import (
            compute_retry_strategy,
            RetryStrategyRequest,
            RetryAction,
        )

        request = RetryStrategyRequest(
            event_id="stripe:evt_fail",
            failure_code="try_again_later",
            amount_cents=5000,
            attempt_count=5,  # Max attempts
        )

        action, delay, confidence, reason = compute_retry_strategy(request)

        assert action == RetryAction.DO_NOT_RETRY
        assert "maximum" in reason.lower()


class TestInferenceModels:
    """Tests for inference data models."""

    def test_fraud_score_request_model(self) -> None:
        """Test FraudScoreRequest model validation."""
        from inference_service.routes.fraud import FraudScoreRequest

        request = FraudScoreRequest(
            event_id="test",
            amount_cents=1000,
            currency="USD",
        )

        assert request.event_id == "test"
        assert request.amount_cents == 1000
        assert request.customer_id is None

    def test_retry_strategy_request_model(self) -> None:
        """Test RetryStrategyRequest model validation."""
        from inference_service.routes.retry import RetryStrategyRequest

        request = RetryStrategyRequest(
            event_id="test",
            amount_cents=1000,
        )

        assert request.event_id == "test"
        assert request.attempt_count == 1  # Default
        assert request.failure_code is None

    def test_retry_action_enum(self) -> None:
        """Test RetryAction enum values."""
        from inference_service.routes.retry import RetryAction

        assert RetryAction.RETRY_NOW.value == "retry_now"
        assert RetryAction.RETRY_DELAYED.value == "retry_delayed"
        assert RetryAction.DO_NOT_RETRY.value == "do_not_retry"
        assert RetryAction.CONTACT_CUSTOMER.value == "contact_customer"


class TestChurnPrediction:
    """Tests for churn prediction logic."""

    def test_low_risk_customer(self) -> None:
        """Test churn scoring for low-risk customer."""
        from inference_service.routes.churn import (
            compute_churn_probability_mock,
            ChurnPredictionRequest,
        )

        request = ChurnPredictionRequest(
            customer_id="cus_loyal",
            total_payments=100,
            successful_payments=98,
            failed_payments=2,
            recovered_payments=2,
            days_since_last_payment=5,
            consecutive_failures=0,
        )

        probability, factors, actions = compute_churn_probability_mock(request)

        assert 0.0 <= probability <= 0.3  # Low risk
        assert "multiple_consecutive_failures" not in factors

    def test_high_risk_customer(self) -> None:
        """Test churn scoring for high-risk customer."""
        from inference_service.routes.churn import (
            compute_churn_probability_mock,
            ChurnPredictionRequest,
        )

        request = ChurnPredictionRequest(
            customer_id="cus_risky",
            total_payments=10,
            successful_payments=5,
            failed_payments=5,
            recovered_payments=1,
            days_since_last_payment=45,
            consecutive_failures=3,
        )

        probability, factors, actions = compute_churn_probability_mock(request)

        assert probability >= 0.5  # High risk
        assert "multiple_consecutive_failures" in factors
        assert len(actions) > 0

    def test_risk_level_thresholds(self) -> None:
        """Test risk level classification."""
        from inference_service.routes.churn import get_risk_level

        assert get_risk_level(0.1) == "low"
        assert get_risk_level(0.24) == "low"
        assert get_risk_level(0.25) == "medium"
        assert get_risk_level(0.49) == "medium"
        assert get_risk_level(0.5) == "high"
        assert get_risk_level(0.74) == "high"
        assert get_risk_level(0.75) == "critical"
        assert get_risk_level(0.99) == "critical"

class TestPaymentRecovery:
    """Tests for payment recovery logic."""

    def test_expired_card_recovery(self) -> None:
        """Test recovery plan for expired card."""
        from inference_service.routes.recovery import (
            compute_recovery_plan,
            PaymentRecoveryRequest,
            RecoveryAction,
        )

        request = PaymentRecoveryRequest(
            event_id="evt_expired",
            customer_id="cus_123",
            amount_cents=5000,
            failure_code="expired_card",
            card_exp_month=1,
            card_exp_year=2020,  # Expired
            has_valid_email=True,
        )

        priority, action, steps, prob, insights = compute_recovery_plan(request)

        assert action == RecoveryAction.UPDATE_PAYMENT_METHOD
        assert "Card is expired" in insights or "expired_card" in str(insights).lower()
        assert any(s.action == RecoveryAction.DUNNING_EMAIL for s in steps)

    def test_transient_failure_recovery(self) -> None:
        """Test recovery plan for transient failure."""
        from inference_service.routes.recovery import (
            compute_recovery_plan,
            PaymentRecoveryRequest,
            RecoveryAction,
        )

        request = PaymentRecoveryRequest(
            event_id="evt_transient",
            customer_id="cus_123",
            amount_cents=5000,
            failure_code="processing_error",
            attempt_number=1,
        )

        priority, action, steps, prob, insights = compute_recovery_plan(request)

        assert action == RecoveryAction.RETRY_OPTIMAL_TIME
        assert prob >= 0.5  # Good success probability for transient
        assert "transient" in str(insights).lower()

    def test_high_value_customer_priority(self) -> None:
        """Test that high-value customers get urgent priority."""
        from inference_service.routes.recovery import (
            compute_recovery_plan,
            PaymentRecoveryRequest,
            RecoveryPriority,
        )

        request = PaymentRecoveryRequest(
            event_id="evt_vip",
            customer_id="cus_vip",
            amount_cents=5000,
            failure_code="processing_error",
            customer_lifetime_value_cents=200_000_00,  # $2000 LTV
        )

        priority, _, _, _, insights = compute_recovery_plan(request)

        assert priority == RecoveryPriority.URGENT
        assert any("high-value" in i.lower() for i in insights)

    def test_backup_payment_method_preferred(self) -> None:
        """Test that backup payment method is used when available."""
        from inference_service.routes.recovery import (
            compute_recovery_plan,
            PaymentRecoveryRequest,
            RecoveryAction,
        )

        request = PaymentRecoveryRequest(
            event_id="evt_backup",
            customer_id="cus_123",
            amount_cents=5000,
            failure_code="insufficient_funds",
            has_backup_payment_method=True,
        )

        priority, action, steps, prob, insights = compute_recovery_plan(request)

        # First step should be to try backup payment method
        assert steps[0].action == RecoveryAction.OFFER_ALTERNATIVE
        assert "backup" in str(insights).lower()

    def test_optimal_retry_hour(self) -> None:
        """Test optimal retry hour calculation."""
        from inference_service.routes.recovery import compute_optimal_retry_hour

        # Insufficient funds - morning hours
        hour = compute_optimal_retry_hour("insufficient_funds", 5000)
        assert 6 <= hour <= 12

        # High value - business hours
        hour_high = compute_optimal_retry_hour("processing_error", 100_000_00)
        assert 9 <= hour_high <= 17

    def test_recovery_action_enum(self) -> None:
        """Test RecoveryAction enum values."""
        from inference_service.routes.recovery import RecoveryAction

        assert RecoveryAction.RETRY_IMMEDIATELY.value == "retry_immediately"
        assert RecoveryAction.DUNNING_EMAIL.value == "dunning_email"
        assert RecoveryAction.UPDATE_PAYMENT_METHOD.value == "update_payment_method"
        assert RecoveryAction.ESCALATE_TO_SUPPORT.value == "escalate_to_support"
