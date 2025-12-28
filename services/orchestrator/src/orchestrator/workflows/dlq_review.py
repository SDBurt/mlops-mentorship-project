"""DLQ review workflow definition."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from ..activities.postgres import persist_quarantine_to_postgres


@dataclass
class DLQReviewResult:
    """Result of DLQ review workflow."""

    event_id: str
    quarantine_success: bool
    quarantine_table: str | None
    failure_reason: str | None


@workflow.defn
class DLQReviewWorkflow:
    """
    Workflow for processing dead letter queue (DLQ) events.

    This workflow handles events that failed validation in the normalizer.
    Currently it persists them to a quarantine table for analysis.

    Future enhancements:
    - Signal-based manual review
    - Automatic reprocessing for certain error types
    - Alerting for high quarantine rates
    """

    def __init__(self) -> None:
        self._status = "initialized"
        self._review_decision: str | None = None

    @workflow.run
    async def run(self, dlq_payload: dict[str, Any]) -> DLQReviewResult:
        """
        Main workflow execution for DLQ events.

        Args:
            dlq_payload: DLQ payload with original event and error details

        Returns:
            DLQReviewResult with quarantine outcome
        """
        event_id = dlq_payload.get("event_id", "unknown")
        workflow.logger.info(f"Processing DLQ event: {event_id}")
        self._status = "processing"

        # Extract failure reason for logging
        failure_reason = dlq_payload.get("failure_reason")
        validation_errors = dlq_payload.get("validation_errors", [])

        workflow.logger.info(
            f"DLQ event {event_id}: failure_reason={failure_reason}, "
            f"error_count={len(validation_errors)}"
        )

        # Step 1: Persist to quarantine table in Postgres
        workflow.logger.info(f"Persisting DLQ event {event_id} to quarantine table")
        quarantine_result = await workflow.execute_activity(
            persist_quarantine_to_postgres,
            dlq_payload,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=10),
                maximum_attempts=5,
                backoff_coefficient=2.0,
            ),
        )

        self._status = "completed"
        workflow.logger.info(f"DLQ review workflow completed for {event_id}")

        return DLQReviewResult(
            event_id=event_id,
            quarantine_success=quarantine_result.get("success", False),
            quarantine_table=quarantine_result.get("table"),
            failure_reason=failure_reason,
        )

    @workflow.query
    def get_status(self) -> str:
        """Query the current workflow status."""
        return self._status

    @workflow.query
    def get_review_decision(self) -> str | None:
        """Query the review decision (for future manual review feature)."""
        return self._review_decision

    @workflow.signal
    def set_review_decision(self, decision: str) -> None:
        """
        Signal to set manual review decision.

        This is a placeholder for future manual review functionality.
        Possible decisions: 'approve', 'reject', 'reprocess'
        """
        workflow.logger.info(f"Received review decision: {decision}")
        self._review_decision = decision
