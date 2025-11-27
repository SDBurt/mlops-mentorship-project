# temporal/workflows/payment_recovery.py
"""
Payment recovery workflow.

Orchestrates the recovery of failed payments using ML-driven retry logic.
This implements the "per-payment approach" where each failed payment gets
its own durable workflow instance.

Key features:
- Per-payment workflow (not batches)
- Durable state across retries
- Long-running timers (hours/days) without holding resources
- Full visibility into payment lifecycle via Temporal UI
- Provider-agnostic processing (Stripe, Square, Braintree)
"""
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal.activities.validate_event import validate_event, ValidationResult
    from temporal.activities.normalize_event import normalize_event, NormalizedFailedPayment
    from temporal.activities.enrich_context import enrich_payment_context, EnrichedPaymentContext
    from temporal.activities.predict_retry_strategy import predict_retry_strategy, RetryPrediction
    from temporal.activities.provider_retry import execute_provider_retry, RetryResult
    from temporal.activities.kafka_emitter import emit_to_kafka
    from temporal.config import config


@workflow.defn
class PaymentRecoveryWorkflow:
    """
    Orchestrates payment recovery with ML-driven retry logic.

    This workflow demonstrates how Butter Payments would process each failed
    payment individually with intelligent retry timing and strategy.
    """

    MAX_RETRY_ATTEMPTS = 5

    @workflow.run
    async def run(self, failed_payment_event: dict) -> dict:
        """
        Execute the payment recovery workflow.

        Args:
            failed_payment_event: FailedPaymentEvent.to_dict()

        Returns:
            Final status of the recovery attempt
        """
        # Get identifiers for logging
        payment_data = failed_payment_event.get("payment", failed_payment_event)
        payment_id = payment_data.get(
            "provider_payment_id",
            payment_data.get("id", "unknown")
        )
        provider = payment_data.get("provider", "unknown")

        workflow.logger.info(
            f"Starting payment recovery: {payment_id} [{provider}]"
        )

        # Step 1: Validate the event
        validation: ValidationResult = await workflow.execute_activity(
            validate_event,
            failed_payment_event,
            start_to_close_timeout=timedelta(seconds=30),
        )

        if not validation.is_valid:
            # Quarantine invalid events
            await self._emit_event("payment.quarantined", {
                "provider": provider,
                "provider_payment_id": payment_id,
                "quarantine_reason": validation.quarantine_reason,
                "errors": [
                    {"field": e.field, "type": e.error_type, "message": e.message}
                    for e in validation.errors
                ],
            })
            workflow.logger.warning(
                f"Payment quarantined: {validation.quarantine_reason}"
            )
            return {
                "status": "quarantined",
                "reason": validation.quarantine_reason,
                "errors": len(validation.errors),
            }

        # Step 2: Normalize the event (once, outside retry loop)
        normalized: NormalizedFailedPayment = await workflow.execute_activity(
            normalize_event,
            failed_payment_event,
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Step 3: Enrich with ML features (once, outside retry loop)
        enriched: EnrichedPaymentContext = await workflow.execute_activity(
            enrich_payment_context,
            normalized.to_dict() if hasattr(normalized, 'to_dict') else normalized,
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Step 4: Retry loop
        attempt = 0
        last_failure_code = normalized.failure_code

        while attempt < self.MAX_RETRY_ATTEMPTS:
            attempt += 1
            workflow.logger.info(f"Recovery attempt {attempt}")

            # 4a. Get ML prediction for this attempt
            prediction: RetryPrediction = await workflow.execute_activity(
                predict_retry_strategy,
                args=[
                    enriched.to_dict() if hasattr(enriched, 'to_dict') else enriched,
                    last_failure_code,
                    attempt,
                ],
                start_to_close_timeout=timedelta(seconds=30),
            )

            # Check if we should give up or request customer action
            if not prediction.should_retry:
                event_type = (
                    "payment.customer_action_required"
                    if prediction.retry_method in ("request_update", "dunning_email")
                    else "payment.unrecoverable"
                )

                await self._emit_event(event_type, {
                    "provider": normalized.provider,
                    "provider_payment_id": normalized.provider_payment_id,
                    "amount_cents": normalized.amount_cents,
                    "currency": normalized.currency,
                    "customer_id": normalized.customer_id,
                    "reason": prediction.reason,
                    "action_required": prediction.retry_method,
                    "attempts": attempt,
                    "model_version": prediction.model_version,
                })

                workflow.logger.info(
                    f"Recovery stopped: {prediction.retry_method} - {prediction.reason}"
                )

                return {
                    "status": prediction.retry_method,
                    "reason": prediction.reason,
                    "attempts": attempt,
                }

            # 4b. Emit retry scheduled event
            await self._emit_event("payment.retry_scheduled", {
                "provider": normalized.provider,
                "provider_payment_id": normalized.provider_payment_id,
                "attempt": attempt,
                "delay_hours": prediction.delay_hours,
                "retry_method": prediction.retry_method,
                "confidence": prediction.confidence,
            })

            # 4c. Wait for optimal retry time (durable timer)
            workflow.logger.info(
                f"Waiting {prediction.delay_hours}h before retry attempt {attempt}"
            )
            await workflow.sleep(timedelta(hours=prediction.delay_hours))

            # 4d. Execute retry via provider API
            # Update retry count in normalized payment
            normalized_dict = normalized.to_dict() if hasattr(normalized, 'to_dict') else normalized
            if isinstance(normalized_dict, dict):
                normalized_dict["retry_count"] = attempt

            result: RetryResult = await workflow.execute_activity(
                execute_provider_retry,
                args=[normalized_dict, prediction.retry_method],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=1),  # Don't auto-retry provider calls
            )

            if result.success:
                # Success! Payment recovered
                await self._emit_event("payment.recovered", {
                    "provider": normalized.provider,
                    "provider_payment_id": normalized.provider_payment_id,
                    "amount_cents": normalized.amount_cents,
                    "currency": normalized.currency,
                    "customer_id": normalized.customer_id,
                    "customer_name": normalized.customer_name,
                    "merchant_name": normalized.merchant_name,
                    "new_charge_id": result.new_charge_id,
                    "attempts": attempt,
                    "total_delay_hours": sum([
                        p.delay_hours for p in [prediction]
                    ]),  # Simplified - would track across attempts
                })

                workflow.logger.info(
                    f"Payment recovered: {result.new_charge_id} after {attempt} attempts"
                )

                return {
                    "status": "recovered",
                    "new_charge_id": result.new_charge_id,
                    "attempts": attempt,
                }

            # 4e. Retry failed - update failure code and emit event
            last_failure_code = result.error_code or last_failure_code

            await self._emit_event("payment.retry_failed", {
                "provider": normalized.provider,
                "provider_payment_id": normalized.provider_payment_id,
                "attempt": attempt,
                "error_code": result.error_code,
                "error_message": result.error_message,
            })

            workflow.logger.warning(
                f"Retry {attempt} failed: {result.error_code} - {result.error_message}"
            )

        # Exhausted all attempts
        await self._emit_event("payment.unrecoverable", {
            "provider": normalized.provider,
            "provider_payment_id": normalized.provider_payment_id,
            "amount_cents": normalized.amount_cents,
            "currency": normalized.currency,
            "customer_id": normalized.customer_id,
            "reason": "max_attempts_exceeded",
            "attempts": attempt,
            "final_error_code": last_failure_code,
        })

        workflow.logger.info(
            f"Payment unrecoverable after {attempt} attempts"
        )

        return {
            "status": "unrecoverable",
            "reason": "max_attempts_exceeded",
            "attempts": attempt,
            "final_error_code": last_failure_code,
        }

    async def _emit_event(self, event_type: str, data: dict) -> None:
        """Emit a payment event to Kafka."""
        event = {
            "event_id": f"evt_{workflow.uuid4().hex[:12]}",
            "type": event_type,
            "created_at": workflow.now().isoformat(),
            "data": data,
        }

        await workflow.execute_activity(
            emit_to_kafka,
            args=[config.kafka.topic_charges, event],
            start_to_close_timeout=timedelta(seconds=30),
        )
