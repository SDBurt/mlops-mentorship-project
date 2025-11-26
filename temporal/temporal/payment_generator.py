# temporal/payment_generator.py
"""
Payment workflow generator.

Generates synthetic payment requests from multiple providers (Stripe, Square, Braintree)
and starts Temporal workflows. This demonstrates the "per-payment approach" where each
payment gets its own durable workflow instance.

Usage:
    uv run python -m temporal.payment_generator
    uv run python -m temporal.payment_generator --rate 5.0
    uv run python -m temporal.payment_generator --count 100
    uv run python -m temporal.payment_generator --provider stripe
    uv run python -m temporal.payment_generator --provider random --count 50
"""
import argparse
import asyncio
import signal
from temporalio.client import Client

from temporal.config import config
from temporal.providers import generate_payment, Provider
from temporal.workflows.payment_processing import PaymentProcessingWorkflow


async def generate_payments(
    rate_per_second: float = 2.0,
    max_count: int | None = None,
    provider: str = "random",
) -> None:
    """
    Generate payment workflow instances.

    Args:
        rate_per_second: Number of payments to generate per second
        max_count: Maximum number of payments to generate (None for unlimited)
        provider: Payment provider ("stripe", "square", "braintree", "random")
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

    print(f"Starting payment generation at {rate_per_second} payments/second")
    if max_count:
        print(f"Will generate {max_count} payments then stop")
    else:
        print("Running indefinitely (Ctrl+C to stop)")

    payment_count = 0
    provider_counts = {"stripe": 0, "square": 0, "braintree": 0}

    while not shutdown_event.is_set():
        payment_count += 1

        if max_count and payment_count > max_count:
            print(f"Reached max count of {max_count} payments")
            break

        # Generate payment from provider
        payment = generate_payment(provider=selected_provider)
        provider_counts[payment.provider] += 1

        # Start workflow with normalized payment data
        workflow_id = f"payment-{payment.provider}-{payment.provider_payment_id}"
        await client.start_workflow(
            PaymentProcessingWorkflow.run,
            payment.to_dict(),
            id=workflow_id,
            task_queue=config.temporal.task_queue,
        )

        amount_display = payment.amount_cents / 100
        print(
            f"[{payment_count}] Started {workflow_id}: "
            f"{payment.currency} {amount_display:.2f} "
            f"from {payment.customer_name} to {payment.merchant_name} "
            f"[{payment.provider}]"
        )

        try:
            await asyncio.wait_for(
                shutdown_event.wait(),
                timeout=1 / rate_per_second
            )
        except asyncio.TimeoutError:
            pass  # Normal timeout, continue generating

    print(f"\nGenerator stopped after {payment_count} payments")
    print(f"Provider distribution: {provider_counts}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate payment workflows for Temporal processing"
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=2.0,
        help="Payments per second (default: 2.0)"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Max number of payments to generate (default: unlimited)"
    )
    parser.add_argument(
        "--provider",
        choices=["stripe", "square", "braintree", "random"],
        default="random",
        help="Payment provider to use (default: random)"
    )

    args = parser.parse_args()

    asyncio.run(generate_payments(
        rate_per_second=args.rate,
        max_count=args.count,
        provider=args.provider,
    ))


if __name__ == "__main__":
    main()
