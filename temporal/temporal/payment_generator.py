# temporal/payment_generator.py
"""
Failed payment event generator for payment recovery workflows.

Generates synthetic failed payment events from multiple providers (Stripe, Square, Braintree)
and starts Temporal recovery workflows. This demonstrates the "per-payment approach" where
each failed payment gets its own durable workflow instance.

Usage:
    uv run python -m temporal.payment_generator
    uv run python -m temporal.payment_generator --rate 5.0
    uv run python -m temporal.payment_generator --count 100
    uv run python -m temporal.payment_generator --provider stripe
    uv run python -m temporal.payment_generator --provider random --count 50
    uv run python -m temporal.payment_generator --failure-code insufficient_funds
"""
import argparse
import asyncio
import signal
from temporalio.client import Client

from temporal.config import config
from temporal.providers import generate_failed_payment, Provider
from temporal.workflows.payment_recovery import PaymentRecoveryWorkflow


async def generate_failed_payments(
    rate_per_second: float = 2.0,
    max_count: int | None = None,
    provider: str = "random",
    failure_code: str | None = None,
) -> None:
    """
    Generate failed payment recovery workflow instances.

    Args:
        rate_per_second: Number of failed payments to generate per second
        max_count: Maximum number of failed payments to generate (None for unlimited)
        provider: Payment provider ("stripe", "square", "braintree", "random")
        failure_code: Specific failure code to use, or None for random
    """
    print(f"Connecting to Temporal at {config.temporal.host}...")
    client = await Client.connect(config.temporal.host)

    # Set up graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler():
        print("\nShutdown signal received, stopping generator...")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # Parse provider selection
    selected_provider: Provider | None = None
    if provider != "random":
        selected_provider = Provider(provider)
        print(f"Using provider: {provider}")
    else:
        print("Using random provider selection (60% Stripe, 25% Square, 15% Braintree)")

    if failure_code:
        print(f"Using failure code: {failure_code}")
    else:
        print("Using random failure codes based on realistic distribution")

    print(f"Starting failed payment generation at {rate_per_second} events/second")
    if max_count:
        print(f"Will generate {max_count} failed payments then stop")
    else:
        print("Running indefinitely (Ctrl+C to stop)")

    event_count = 0
    provider_counts = {"stripe": 0, "square": 0, "braintree": 0}
    failure_counts: dict[str, int] = {}

    while not shutdown_event.is_set():
        event_count += 1

        if max_count and event_count > max_count:
            print(f"Reached max count of {max_count} failed payments")
            break

        # Generate failed payment event from provider
        failed_event = generate_failed_payment(
            provider=selected_provider,
            failure_code=failure_code,
        )
        provider_counts[failed_event.payment.provider] += 1
        failure_counts[failed_event.failure_code] = (
            failure_counts.get(failed_event.failure_code, 0) + 1
        )

        # Start recovery workflow with failed payment event
        workflow_id = (
            f"recovery-{failed_event.payment.provider}-"
            f"{failed_event.payment.provider_payment_id}"
        )
        await client.start_workflow(
            PaymentRecoveryWorkflow.run,
            failed_event.to_dict(),
            id=workflow_id,
            task_queue=config.temporal.task_queue,
        )

        amount_display = failed_event.payment.amount_cents / 100
        print(
            f"[{event_count}] Started {workflow_id}: "
            f"{failed_event.payment.currency} {amount_display:.2f} "
            f"from {failed_event.payment.customer_name} "
            f"[{failed_event.payment.provider}] "
            f"- {failed_event.failure_code}"
        )

        try:
            await asyncio.wait_for(
                shutdown_event.wait(),
                timeout=1 / rate_per_second
            )
        except asyncio.TimeoutError:
            pass  # Normal timeout, continue generating

    print(f"\nGenerator stopped after {event_count} failed payment events")
    print(f"Provider distribution: {provider_counts}")
    print(f"Failure code distribution: {failure_counts}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate failed payment events for Temporal recovery workflows"
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=2.0,
        help="Failed payments per second (default: 2.0)"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Max number of failed payments to generate (default: unlimited)"
    )
    parser.add_argument(
        "--provider",
        choices=["stripe", "square", "braintree", "random"],
        default="random",
        help="Payment provider to use (default: random)"
    )
    parser.add_argument(
        "--failure-code",
        type=str,
        default=None,
        help="Specific failure code (e.g., 'insufficient_funds', 'card_declined')"
    )

    args = parser.parse_args()

    asyncio.run(generate_failed_payments(
        rate_per_second=args.rate,
        max_count=args.count,
        provider=args.provider,
        failure_code=args.failure_code,
    ))


if __name__ == "__main__":
    main()
