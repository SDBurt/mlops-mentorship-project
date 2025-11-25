# temporal/workflows/payment_processing.py
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
import uuid

with workflow.unsafe.imports_passed_through():
    from temporal.activities import (
        check_fraud, charge_payment, get_retry_strategy, emit_to_kafka
    )
    from temporal.activities.charge_payment import PaymentDeclinedError

@workflow.defn
class PaymentProcessingWorkflow:
    """
    Orchestrates individual payment processing with ML-driven retry logic.

    This demonstrates Temporal's key strengths for Butter Payments:
    - Per-payment workflow (not batches)
    - Durable state across retries
    - Long-running timers (hours/days) without holding resources
    - Full visibility into payment lifecycle
    """

    @workflow.run
    async def run(self, payment_request: dict) -> dict:
        workflow.logger.info(f"Starting payment workflow: {payment_request.get('transaction_id')}")

        # Step 1: Fraud check (no retries - immediate decision)
        fraud_result = await workflow.execute_activity(
            check_fraud,
            payment_request,
            start_to_close_timeout=timedelta(seconds=10),
        )

        if not fraud_result.is_safe:
            event = self._create_event("charge.blocked", payment_request, {
                "fraud_score": fraud_result.risk_score,
                "block_reasons": fraud_result.reasons
            })
            await self._emit_event("payment_charges", event)
            return event

        # Step 2: Attempt payment with retry logic
        attempt = 0
        max_workflow_attempts = 5

        while attempt < max_workflow_attempts:
            attempt += 1
            workflow.logger.info(f"Payment attempt {attempt}")

            try:
                charge_result = await workflow.execute_activity(
                    charge_payment,
                    payment_request,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=1),  # Handle retries ourselves
                )

                # Success
                event = self._create_event("charge.succeeded", payment_request, {
                    "charge_id": charge_result.charge_id,
                    "amount_charged": charge_result.amount_charged,
                    "attempts": attempt
                })
                await self._emit_event("payment_charges", event)
                return event

            except PaymentDeclinedError as e:
                workflow.logger.warning(f"Payment declined: {e.code}")

                # Get ML-driven retry strategy
                strategy = await workflow.execute_activity(
                    get_retry_strategy,
                    args=[payment_request, e.code, attempt],
                    start_to_close_timeout=timedelta(seconds=10),
                )

                if not strategy.should_retry:
                    # Final failure
                    event = self._create_event("charge.failed", payment_request, {
                        "failure_code": e.code,
                        "attempts": attempt,
                        "final_strategy": strategy.method
                    })
                    await self._emit_event("payment_charges", event)
                    return event

                # Durable timer - workflow sleeps without holding resources
                workflow.logger.info(f"Waiting {strategy.delay_hours}h before retry")
                await workflow.sleep(timedelta(hours=strategy.delay_hours))

        # Exhausted all attempts
        event = self._create_event("charge.failed", payment_request, {
            "failure_code": "max_attempts_exceeded",
            "attempts": attempt
        })
        await self._emit_event("payment_charges", event)
        return event

    def _create_event(self, event_type: str, payment: dict, data: dict) -> dict:
        return {
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "type": event_type,
            "created_at": workflow.now().isoformat(),
            "data": {**payment, **data}
        }

    async def _emit_event(self, topic: str, event: dict) -> None:
        await workflow.execute_activity(
            emit_to_kafka,
            args=[topic, event],
            start_to_close_timeout=timedelta(seconds=10),
        )
