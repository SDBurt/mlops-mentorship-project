"""Payment event workflow definition."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from ..activities.validation import validate_business_rules
    from ..activities.fraud import get_fraud_score
    from ..activities.retry_strategy import get_retry_strategy
    from ..activities.churn import get_churn_prediction
    from ..activities.postgres import persist_to_postgres


@dataclass
class PaymentProcessingResult:
    """Result of payment event processing workflow."""

    event_id: str
    validation_status: str
    validation_errors: list[dict[str, Any]]
    fraud_score: float | None
    risk_level: str | None
    retry_strategy: dict[str, Any] | None
    churn_score: float | None
    churn_risk_level: str | None
    persistence_success: bool
    persistence_table: str | None


@workflow.defn
class PaymentEventWorkflow:
    """
    Workflow for processing normalized payment events.

    This workflow executes a series of activities:
    1. Validate business rules
    2. Get fraud score (for successful payments)
    3. Get retry strategy (for failed payments)
    4. Persist to Iceberg Bronze layer

    The workflow is idempotent - using event_id as workflow ID ensures
    duplicate events are not processed twice.
    """

    def __init__(self) -> None:
        self._status = "initialized"
        self._fraud_score: float | None = None
        self._risk_level: str | None = None
        self._retry_strategy: dict[str, Any] | None = None
        self._churn_score: float | None = None
        self._churn_risk_level: str | None = None

    @workflow.run
    async def run(self, event_data: dict[str, Any]) -> PaymentProcessingResult:
        """
        Main workflow execution.

        Args:
            event_data: Normalized payment event data

        Returns:
            PaymentProcessingResult with processing outcomes
        """
        event_id = event_data.get("event_id", "unknown")
        workflow.logger.info(f"Processing payment event: {event_id}")
        self._status = "processing"

        # Step 1: Validate business rules
        workflow.logger.info(f"Step 1: Validating business rules for {event_id}")
        validation_result = await workflow.execute_activity(
            validate_business_rules,
            event_data,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=10),
                maximum_attempts=3,
                backoff_coefficient=2.0,
            ),
        )

        # Update event data with validation result
        if validation_result["is_valid"]:
            event_data["validation_status"] = "passed"
        else:
            event_data["validation_status"] = "failed"
            event_data["validation_errors"] = validation_result["errors"]

        # Step 2: Get fraud score (for successful/captured payments)
        event_status = event_data.get("status", "").lower()
        event_type = event_data.get("event_type", "").lower()

        is_successful_payment = any([
            "succeeded" in event_status,
            "captured" in event_status,
            "succeeded" in event_type,
            "captured" in event_type,
        ])

        if is_successful_payment:
            workflow.logger.info(f"Step 2: Getting fraud score for {event_id}")
            try:
                fraud_result = await workflow.execute_activity(
                    get_fraud_score,
                    event_data,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=2),
                        maximum_interval=timedelta(seconds=30),
                        maximum_attempts=5,
                        backoff_coefficient=2.0,
                    ),
                )
                self._fraud_score = fraud_result.get("fraud_score")
                self._risk_level = fraud_result.get("risk_level")
                event_data["fraud_score"] = self._fraud_score
                event_data["risk_level"] = self._risk_level
                event_data["risk_factors"] = fraud_result.get("risk_factors", [])
            except Exception as e:
                workflow.logger.warning(f"Fraud scoring failed for {event_id}: {e}")
                # Continue without fraud score - it's not critical
                event_data["fraud_score"] = None
                event_data["risk_level"] = "unknown"

        # Step 3: Get retry strategy (for failed payments)
        is_failed_payment = any([
            "failed" in event_status,
            "failed" in event_type,
            "declined" in event_status,
        ])

        if is_failed_payment:
            workflow.logger.info(f"Step 3: Getting retry strategy for {event_id}")
            try:
                self._retry_strategy = await workflow.execute_activity(
                    get_retry_strategy,
                    event_data,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=2),
                        maximum_interval=timedelta(seconds=30),
                        maximum_attempts=5,
                        backoff_coefficient=2.0,
                    ),
                )
                event_data["retry_strategy"] = self._retry_strategy
            except Exception as e:
                workflow.logger.warning(f"Retry strategy failed for {event_id}: {e}")
                # Continue without retry strategy
                self._retry_strategy = None

        # Step 4: Get churn prediction (for any event with customer_id)
        workflow.logger.info(f"Step 4: Getting churn prediction for {event_id}")
        try:
            churn_result = await workflow.execute_activity(
                get_churn_prediction,
                event_data,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=5,
                    backoff_coefficient=2.0,
                ),
            )
            self._churn_score = churn_result.get("churn_score")
            self._churn_risk_level = churn_result.get("churn_risk_level")
            event_data["churn_score"] = self._churn_score
            event_data["churn_risk_level"] = self._churn_risk_level
            event_data["days_to_churn_estimate"] = churn_result.get("days_to_churn_estimate")
        except Exception as e:
            workflow.logger.warning(f"Churn prediction failed for {event_id}: {e}")
            # Continue without churn prediction - it's not critical
            event_data["churn_score"] = None
            event_data["churn_risk_level"] = None

        # Step 5: Persist to Postgres (Bronze staging layer)
        workflow.logger.info(f"Step 5: Persisting to Postgres for {event_id}")
        persistence_result = await workflow.execute_activity(
            persist_to_postgres,
            event_data,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=10),
                maximum_attempts=5,
                backoff_coefficient=2.0,
            ),
        )

        self._status = "completed"
        workflow.logger.info(f"Payment event workflow completed for {event_id}")

        return PaymentProcessingResult(
            event_id=event_id,
            validation_status=event_data.get("validation_status", "unknown"),
            validation_errors=validation_result.get("errors", []),
            fraud_score=self._fraud_score,
            risk_level=self._risk_level,
            retry_strategy=self._retry_strategy,
            churn_score=self._churn_score,
            churn_risk_level=self._churn_risk_level,
            persistence_success=persistence_result.get("success", False),
            persistence_table=persistence_result.get("table"),
        )

    @workflow.query
    def get_status(self) -> str:
        """Query the current workflow status."""
        return self._status

    @workflow.query
    def get_fraud_score(self) -> float | None:
        """Query the fraud score (if computed)."""
        return self._fraud_score

    @workflow.query
    def get_retry_strategy(self) -> dict[str, Any] | None:
        """Query the retry strategy (if computed)."""
        return self._retry_strategy

    @workflow.query
    def get_churn_score(self) -> float | None:
        """Query the churn score (if computed)."""
        return self._churn_score
