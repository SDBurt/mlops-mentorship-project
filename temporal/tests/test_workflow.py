# tests/test_workflow.py
"""
Integration tests for PaymentProcessingWorkflow.

Uses Temporal's time-skipping test environment for fast timer testing.
"""
import pytest
from dataclasses import dataclass
from temporalio import activity
from temporalio.worker import Worker
from temporalio.testing import WorkflowEnvironment

from temporal.workflows.payment_processing import PaymentProcessingWorkflow
from temporal.activities.fraud_check import FraudCheckResult
from temporal.activities.charge_payments import ChargeResult, PaymentDeclinedError
from temporal.activities.retry_strategy import RetryStrategy


@dataclass
class MockConfig:
    """Configuration for mock activity behavior."""
    fraud_is_safe: bool = True
    fraud_risk_score: float = 0.1
    fraud_risk_level: str = "normal"
    charge_succeeds: bool = True
    charge_fail_code: str = "card_declined"
    charge_succeed_on_attempt: int = 1
    retry_should_retry: bool = True
    retry_delay_hours: int = 24
    retry_max_attempts: int = 3


# Global config modified by tests
_mock_config = MockConfig()
_charge_attempt_count = 0


@activity.defn(name="check_fraud")
async def mock_check_fraud(payment_data: dict) -> FraudCheckResult:
    """Mock fraud check activity."""
    return FraudCheckResult(
        is_safe=_mock_config.fraud_is_safe,
        risk_score=_mock_config.fraud_risk_score,
        risk_level=_mock_config.fraud_risk_level,
        reasons=[] if _mock_config.fraud_is_safe else ["high_risk"]
    )


@activity.defn(name="charge_payment")
async def mock_charge_payment(payment_data: dict) -> ChargeResult:
    """Mock charge payment activity."""
    global _charge_attempt_count
    _charge_attempt_count += 1

    if (_charge_attempt_count >= _mock_config.charge_succeed_on_attempt
            and _mock_config.charge_succeeds):
        return ChargeResult(
            status="succeeded",
            charge_id=f"ch_mock_{_charge_attempt_count}",
            amount_charged=payment_data.get("amount_cents", 5000)
        )

    raise PaymentDeclinedError(_mock_config.charge_fail_code)


@activity.defn(name="get_retry_strategy")
async def mock_get_retry_strategy(
    payment_data: dict,
    failure_code: str,
    attempt: int
) -> RetryStrategy:
    """Mock retry strategy activity."""
    if attempt >= _mock_config.retry_max_attempts:
        return RetryStrategy(
            should_retry=False,
            delay_hours=0,
            method="give_up",
            max_attempts=_mock_config.retry_max_attempts
        )
    return RetryStrategy(
        should_retry=_mock_config.retry_should_retry,
        delay_hours=_mock_config.retry_delay_hours,
        method="same_card",
        max_attempts=_mock_config.retry_max_attempts
    )


@activity.defn(name="emit_to_kafka")
async def mock_emit_to_kafka(topic: str, event: dict) -> None:
    """Mock Kafka emission - no-op for tests."""
    pass


@pytest.fixture
def sample_payment() -> dict:
    """Sample normalized payment for testing."""
    return {
        "provider": "stripe",
        "provider_payment_id": "pi_test123",
        "amount_cents": 5000,
        "currency": "USD",
        "customer_id": "cus_456",
        "fraud_signals": {"cvc_check": "pass"}
    }


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset mock state before each test."""
    global _mock_config, _charge_attempt_count
    _mock_config = MockConfig()
    _charge_attempt_count = 0
    yield
    _mock_config = MockConfig()
    _charge_attempt_count = 0


class TestPaymentWorkflowIntegration:
    """Integration tests for PaymentProcessingWorkflow with time skipping."""

    @pytest.mark.asyncio
    async def test_successful_payment_flow(self, sample_payment):
        """Payment succeeds on first attempt."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[PaymentProcessingWorkflow],
                activities=[
                    mock_check_fraud,
                    mock_charge_payment,
                    mock_get_retry_strategy,
                    mock_emit_to_kafka
                ],
            ):
                result = await env.client.execute_workflow(
                    PaymentProcessingWorkflow.run,
                    sample_payment,
                    id="test-payment-success",
                    task_queue="test-queue",
                )

                assert result["type"] == "charge.succeeded"
                assert result["data"]["attempts"] == 1
                assert "charge_id" in result["data"]
                assert result["data"]["amount_charged"] == 5000

    @pytest.mark.asyncio
    async def test_fraud_blocked_flow(self, sample_payment):
        """High risk payment is blocked."""
        global _mock_config
        _mock_config.fraud_is_safe = False
        _mock_config.fraud_risk_level = "high"
        _mock_config.fraud_risk_score = 0.9

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[PaymentProcessingWorkflow],
                activities=[
                    mock_check_fraud,
                    mock_charge_payment,
                    mock_get_retry_strategy,
                    mock_emit_to_kafka
                ],
            ):
                result = await env.client.execute_workflow(
                    PaymentProcessingWorkflow.run,
                    sample_payment,
                    id="test-fraud-block",
                    task_queue="test-queue",
                )

                assert result["type"] == "charge.blocked"
                assert result["data"]["risk_level"] == "high"
                assert result["data"]["fraud_score"] == 0.9

    @pytest.mark.asyncio
    async def test_retry_with_time_skipping(self, sample_payment):
        """Payment fails then succeeds after retry delay.

        Time skipping automatically fast-forwards the 48-hour sleep.
        """
        global _mock_config
        _mock_config.charge_succeed_on_attempt = 2  # Fail first, succeed second
        _mock_config.retry_delay_hours = 48

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[PaymentProcessingWorkflow],
                activities=[
                    mock_check_fraud,
                    mock_charge_payment,
                    mock_get_retry_strategy,
                    mock_emit_to_kafka
                ],
            ):
                result = await env.client.execute_workflow(
                    PaymentProcessingWorkflow.run,
                    sample_payment,
                    id="test-retry",
                    task_queue="test-queue",
                )

                assert result["type"] == "charge.succeeded"
                assert result["data"]["attempts"] == 2

    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self, sample_payment):
        """All attempts fail, workflow gives up."""
        global _mock_config
        _mock_config.charge_succeeds = False  # Never succeed
        _mock_config.retry_max_attempts = 3
        _mock_config.retry_delay_hours = 1

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[PaymentProcessingWorkflow],
                activities=[
                    mock_check_fraud,
                    mock_charge_payment,
                    mock_get_retry_strategy,
                    mock_emit_to_kafka
                ],
            ):
                result = await env.client.execute_workflow(
                    PaymentProcessingWorkflow.run,
                    sample_payment,
                    id="test-max-attempts",
                    task_queue="test-queue",
                )

                assert result["type"] == "charge.failed"
                assert result["data"]["final_strategy"] == "give_up"

    @pytest.mark.asyncio
    async def test_no_retry_expired_card(self, sample_payment):
        """Expired card fails immediately without retry."""
        global _mock_config
        _mock_config.charge_succeeds = False
        _mock_config.charge_fail_code = "expired_card"
        _mock_config.retry_should_retry = False  # No retry for expired cards

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[PaymentProcessingWorkflow],
                activities=[
                    mock_check_fraud,
                    mock_charge_payment,
                    mock_get_retry_strategy,
                    mock_emit_to_kafka
                ],
            ):
                result = await env.client.execute_workflow(
                    PaymentProcessingWorkflow.run,
                    sample_payment,
                    id="test-expired-card",
                    task_queue="test-queue",
                )

                assert result["type"] == "charge.failed"
                assert result["data"]["failure_code"] == "expired_card"
                assert result["data"]["attempts"] == 1
