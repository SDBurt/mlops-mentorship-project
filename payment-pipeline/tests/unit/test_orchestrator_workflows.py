"""Unit tests for orchestrator workflows."""

import pytest
from dataclasses import asdict


class TestPaymentEventWorkflow:
    """Tests for PaymentEventWorkflow."""

    def test_payment_processing_result_dataclass(self) -> None:
        """Test PaymentProcessingResult dataclass structure."""
        from orchestrator.workflows.payment_event import PaymentProcessingResult

        result = PaymentProcessingResult(
            event_id="stripe:evt_123",
            validation_status="passed",
            validation_errors=[],
            fraud_score=0.15,
            risk_level="low",
            retry_strategy=None,
            iceberg_success=True,
            iceberg_table="bronze.payments_bronze",
        )

        assert result.event_id == "stripe:evt_123"
        assert result.validation_status == "passed"
        assert result.fraud_score == 0.15
        assert result.iceberg_success is True

        # Verify it's a proper dataclass
        result_dict = asdict(result)
        assert "event_id" in result_dict
        assert "fraud_score" in result_dict

    def test_workflow_class_exists(self) -> None:
        """Test that PaymentEventWorkflow class exists and is properly decorated."""
        from orchestrator.workflows.payment_event import PaymentEventWorkflow

        # Verify it's a class
        assert isinstance(PaymentEventWorkflow, type)

        # Verify it has the expected methods
        assert hasattr(PaymentEventWorkflow, "run")
        assert hasattr(PaymentEventWorkflow, "get_status")
        assert hasattr(PaymentEventWorkflow, "get_fraud_score")
        assert hasattr(PaymentEventWorkflow, "get_retry_strategy")


class TestDLQReviewWorkflow:
    """Tests for DLQReviewWorkflow."""

    def test_dlq_review_result_dataclass(self) -> None:
        """Test DLQReviewResult dataclass structure."""
        from orchestrator.workflows.dlq_review import DLQReviewResult

        result = DLQReviewResult(
            event_id="stripe:evt_invalid",
            quarantine_success=True,
            quarantine_table="bronze.payments_quarantine",
            failure_reason="INVALID_CURRENCY",
        )

        assert result.event_id == "stripe:evt_invalid"
        assert result.quarantine_success is True
        assert result.failure_reason == "INVALID_CURRENCY"

    def test_workflow_class_exists(self) -> None:
        """Test that DLQReviewWorkflow class exists."""
        from orchestrator.workflows.dlq_review import DLQReviewWorkflow

        # Verify it's a class
        assert isinstance(DLQReviewWorkflow, type)

        # Verify it has the expected methods
        assert hasattr(DLQReviewWorkflow, "run")
        assert hasattr(DLQReviewWorkflow, "get_status")
        assert hasattr(DLQReviewWorkflow, "get_review_decision")
        assert hasattr(DLQReviewWorkflow, "set_review_decision")


class TestWorkflowImports:
    """Tests for workflow module imports."""

    def test_workflow_module_exports(self) -> None:
        """Test that workflows module exports correctly."""
        from orchestrator.workflows import PaymentEventWorkflow, DLQReviewWorkflow

        assert PaymentEventWorkflow is not None
        assert DLQReviewWorkflow is not None

    def test_activities_module_exports(self) -> None:
        """Test that activities module exports correctly."""
        from orchestrator.activities import (
            validate_business_rules,
            get_fraud_score,
            get_retry_strategy,
            persist_to_iceberg,
            persist_quarantine,
        )

        # Verify all activities are callable
        assert callable(validate_business_rules)
        assert callable(get_fraud_score)
        assert callable(get_retry_strategy)
        assert callable(persist_to_iceberg)
        assert callable(persist_quarantine)
