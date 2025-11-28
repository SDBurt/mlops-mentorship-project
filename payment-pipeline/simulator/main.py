"""CLI entry point for the webhook simulator."""

import asyncio
import logging
import os
import sys

import click

from simulator.stripe_generator import StripeWebhookSimulator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default values from environment
DEFAULT_GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000/webhooks/stripe/")
DEFAULT_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret_for_dev")

# Available event types for help text
AVAILABLE_EVENT_TYPES = [
    "payment_intent.created",
    "payment_intent.succeeded",
    "payment_intent.payment_failed",
    "payment_intent.canceled",
    "charge.succeeded",
    "charge.failed",
    "charge.pending",
    "charge.captured",
    "charge.refunded",
    "refund.created",
    "refund.updated",
    "refund.failed",
]


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
def cli(debug: bool):
    """Webhook simulator for testing the payment gateway."""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option(
    "--url",
    default=DEFAULT_GATEWAY_URL,
    help="Gateway webhook URL",
    show_default=True,
)
@click.option(
    "--secret",
    default=DEFAULT_WEBHOOK_SECRET,
    help="Webhook signing secret",
)
@click.option(
    "--type",
    "event_type",
    default="payment_intent.succeeded",
    help="Event type to send",
    show_default=True,
)
@click.option(
    "--invalid-signature",
    is_flag=True,
    help="Send with invalid signature (for DLQ testing)",
)
@click.option(
    "--count",
    default=1,
    help="Number of events to send",
    show_default=True,
)
def send(url: str, secret: str, event_type: str, invalid_signature: bool, count: int):
    """Send one or more webhook events to the gateway."""
    if event_type not in AVAILABLE_EVENT_TYPES:
        click.echo(f"Warning: '{event_type}' is not in the known event types list.")
        click.echo(f"Available types: {', '.join(AVAILABLE_EVENT_TYPES)}")
        if not click.confirm("Continue anyway?"):
            sys.exit(1)

    simulator = StripeWebhookSimulator(gateway_url=url, webhook_secret=secret)

    async def run():
        for i in range(count):
            click.echo(f"Sending event {i + 1}/{count}: {event_type}")
            try:
                response = await simulator.send_webhook(
                    event_type=event_type,
                    invalid_signature=invalid_signature,
                )
                result = response.json()
                click.echo(f"  Status: {result.get('status')}")
                click.echo(f"  Event ID: {result.get('event_id', 'N/A')}")
                click.echo(f"  Kafka Topic: {result.get('kafka_topic', 'N/A')}")
                if result.get("message"):
                    click.echo(f"  Message: {result.get('message')}")
            except Exception as e:
                click.echo(f"  Error: {e}", err=True)

    asyncio.run(run())


@cli.command()
@click.option(
    "--url",
    default=DEFAULT_GATEWAY_URL,
    help="Gateway webhook URL",
    show_default=True,
)
@click.option(
    "--secret",
    default=DEFAULT_WEBHOOK_SECRET,
    help="Webhook signing secret",
)
@click.option(
    "--rate",
    default=1.0,
    help="Events per second",
    show_default=True,
)
@click.option(
    "--duration",
    default=60,
    help="Duration in seconds",
    show_default=True,
)
@click.option(
    "--failure-rate",
    default=0.1,
    help="Probability of generating failed payment events",
    show_default=True,
)
@click.option(
    "--invalid-signature-rate",
    default=0.0,
    help="Probability of sending invalid signatures (for DLQ testing)",
    show_default=True,
)
def generate(
    url: str,
    secret: str,
    rate: float,
    duration: int,
    failure_rate: float,
    invalid_signature_rate: float,
):
    """Generate continuous webhook traffic."""
    click.echo(f"Starting traffic generation:")
    click.echo(f"  URL: {url}")
    click.echo(f"  Rate: {rate} events/sec")
    click.echo(f"  Duration: {duration} seconds")
    click.echo(f"  Expected events: {int(rate * duration)}")
    click.echo(f"  Failure rate: {failure_rate * 100}%")
    click.echo(f"  Invalid signature rate: {invalid_signature_rate * 100}%")
    click.echo()

    simulator = StripeWebhookSimulator(gateway_url=url, webhook_secret=secret)

    async def run():
        stats = await simulator.generate_traffic(
            events_per_second=rate,
            duration_seconds=duration,
            failure_rate=failure_rate,
            invalid_signature_rate=invalid_signature_rate,
        )
        click.echo()
        click.echo("Results:")
        click.echo(f"  Total sent: {stats['sent']}")
        click.echo(f"  Successful: {stats['success']}")
        click.echo(f"  Failed: {stats['failed']}")
        click.echo(f"  DLQ tests: {stats['dlq_test']}")

    asyncio.run(run())


@cli.command()
def list_events():
    """List all available event types."""
    click.echo("Available Stripe event types:")
    click.echo()
    for event_type in AVAILABLE_EVENT_TYPES:
        click.echo(f"  - {event_type}")


@cli.command()
@click.option(
    "--type",
    "event_type",
    default="payment_intent.succeeded",
    help="Event type to preview",
)
@click.option(
    "--secret",
    default=DEFAULT_WEBHOOK_SECRET,
    help="Webhook signing secret (for signature preview)",
)
def preview(event_type: str, secret: str):
    """Preview a generated webhook event (without sending)."""
    import json

    simulator = StripeWebhookSimulator(gateway_url="http://example.com", webhook_secret=secret)

    try:
        event = simulator.generate_event(event_type)
        payload = json.dumps(event, indent=2)
        signature = simulator.sign_payload(payload.encode())

        click.echo("Generated Event:")
        click.echo(payload)
        click.echo()
        click.echo(f"Stripe-Signature: {signature}")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
