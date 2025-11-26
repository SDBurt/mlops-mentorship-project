# temporal/workflows/payment_processing.py
"""
Payment processing workflow.

Orchestrates individual payment processing with ML-driven retry logic.
Works with normalized payment data from any provider (Stripe, Square, Braintree).
"""
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from temporal.activities import (
        check_fraud, charge_payment, get_retry_strategy, emit_to_kafka,
    )


@workflow.defn
class PaymentProcessingWorkflow:
    """
    Orchestrates individual payment processing with ML-driven retry logic.

    This demonstrates Temporal's key strengths for Butter Payments:
    - Per-payment workflow (not batches)
    - Durable state across retries
    - Long-running timers (hours/days) without holding resources
    - Full visibility into payment lifecycle
    - Provider-agnostic processing (Stripe, Square, Braintree)
    """

    @workflow.run
    async def run(self, payment_request: dict) -> dict:
        # Get payment identifier (works with normalized and legacy schemas)
        payment_id = payment_request.get(
            'provider_payment_id',
            payment_request.get('id', payment_request.get('transaction_id', 'unknown'))
        )
        provider = payment_request.get('provider', 'unknown')
        workflow.logger.info(f"Starting payment workflow: {payment_id} [{provider}]")

        # Step 1: Fraud check (no retries - immediate decision)
        fraud_result = await workflow.execute_activity(
            check_fraud,
            payment_request,
            start_to_close_timeout=timedelta(seconds=10),
        )

        if not fraud_result.is_safe:
            event = self._create_event("charge.blocked", payment_request, {
                "fraud_score": fraud_result.risk_score,
                "risk_level": fraud_result.risk_level,
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

            except ActivityError as e:
                # Extract the failure code from the wrapped exception
                # ActivityError wraps the original PaymentDeclinedError
                failure_code = "unknown"
                if e.cause and isinstance(e.cause, ApplicationError):
                    # The message contains the decline reason
                    failure_code = e.cause.message.replace("Payment declined: ", "")

                workflow.logger.warning(f"Payment declined: {failure_code}")

                # Get ML-driven retry strategy
                strategy = await workflow.execute_activity(
                    get_retry_strategy,
                    args=[payment_request, failure_code, attempt],
                    start_to_close_timeout=timedelta(seconds=10),
                )

                if not strategy.should_retry:
                    # Final failure
                    event = self._create_event("charge.failed", payment_request, {
                        "failure_code": failure_code,
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
        """Create a payment event with provider information."""
        # Extract key fields for event (exclude raw_provider_data to reduce payload)
        event_data = {
            "provider": payment.get("provider", "unknown"),
            "provider_payment_id": payment.get(
                "provider_payment_id",
                payment.get("id", "unknown")
            ),
            "amount_cents": payment.get("amount_cents", payment.get("amount", 0)),
            "currency": payment.get("currency", "USD"),
            "customer_id": payment.get("customer_id", payment.get("customer", "")),
            "customer_name": payment.get("customer_name", ""),
            "merchant_name": payment.get("merchant_name", ""),
            **data
        }
        return {
            "event_id": f"evt_{workflow.uuid4().hex[:12]}",
            "type": event_type,
            "provider": payment.get("provider", "unknown"),
            "created_at": workflow.now().isoformat(),
            "data": event_data
        }

    async def _emit_event(self, topic: str, event: dict) -> None:
        await workflow.execute_activity(
            emit_to_kafka,
            args=[topic, event],
            start_to_close_timeout=timedelta(seconds=10),
        )
