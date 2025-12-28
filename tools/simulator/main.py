"""CLI entry point for the webhook simulator."""

import asyncio
import logging
import os
import sys

import click

from simulator.adyen_generator import AdyenWebhookSimulator
from simulator.braintree_generator import BraintreeWebhookSimulator
from simulator.square_generator import SquareWebhookSimulator
from simulator.stripe_generator import StripeWebhookSimulator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default values from environment - Stripe
DEFAULT_GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000/webhooks/stripe/")
DEFAULT_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret_for_dev")

# Default values from environment - Square
DEFAULT_SQUARE_GATEWAY_URL = os.getenv(
    "SQUARE_GATEWAY_URL", "http://localhost:8000/webhooks/square/"
)
DEFAULT_SQUARE_SIGNATURE_KEY = os.getenv(
    "SQUARE_WEBHOOK_SIGNATURE_KEY", "sq_signature_key_for_dev"
)
DEFAULT_SQUARE_NOTIFICATION_URL = os.getenv(
    "SQUARE_NOTIFICATION_URL", "http://localhost:8000/webhooks/square/"
)

# Default values from environment - Adyen
DEFAULT_ADYEN_GATEWAY_URL = os.getenv(
    "ADYEN_GATEWAY_URL", "http://localhost:8000/webhooks/adyen/"
)
# 32-byte hex key (64 characters) - example dev key
DEFAULT_ADYEN_HMAC_KEY = os.getenv(
    "ADYEN_HMAC_KEY", "44782DEF547AAA06C910C43932B1EB0C71FC68D9D0C057550C48EC2ACF6BA056"  # pragma: allowlist secret
)

# Default values from environment - Braintree
DEFAULT_BRAINTREE_GATEWAY_URL = os.getenv(
    "BRAINTREE_GATEWAY_URL", "http://localhost:8000/webhooks/braintree/"
)
DEFAULT_BRAINTREE_MERCHANT_ID = os.getenv("BRAINTREE_MERCHANT_ID", "")
DEFAULT_BRAINTREE_PUBLIC_KEY = os.getenv("BRAINTREE_PUBLIC_KEY", "")
DEFAULT_BRAINTREE_PRIVATE_KEY = os.getenv("BRAINTREE_PRIVATE_KEY", "")

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


# =============================================================================
# Square Commands
# =============================================================================

AVAILABLE_SQUARE_EVENT_TYPES = [
    "payment.created",
    "payment.completed",
    "payment.updated",
    "refund.created",
    "refund.updated",
]


@cli.group()
def square():
    """Square webhook commands."""
    pass


@square.command("send")
@click.option(
    "--url",
    default=DEFAULT_SQUARE_GATEWAY_URL,
    help="Gateway webhook URL",
    show_default=True,
)
@click.option(
    "--signature-key",
    default=DEFAULT_SQUARE_SIGNATURE_KEY,
    help="Square webhook signature key",
)
@click.option(
    "--notification-url",
    default=DEFAULT_SQUARE_NOTIFICATION_URL,
    help="Notification URL for signature verification",
)
@click.option(
    "--type",
    "event_type",
    default="payment.completed",
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
def square_send(
    url: str,
    signature_key: str,
    notification_url: str,
    event_type: str,
    invalid_signature: bool,
    count: int,
):
    """Send one or more Square webhook events to the gateway."""
    if event_type not in AVAILABLE_SQUARE_EVENT_TYPES:
        click.echo(f"Warning: '{event_type}' is not in the known event types list.")
        click.echo(f"Available types: {', '.join(AVAILABLE_SQUARE_EVENT_TYPES)}")
        if not click.confirm("Continue anyway?"):
            sys.exit(1)

    simulator = SquareWebhookSimulator(
        gateway_url=url,
        signature_key=signature_key,
        notification_url=notification_url,
    )

    async def run():
        for i in range(count):
            click.echo(f"Sending Square event {i + 1}/{count}: {event_type}")
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


@square.command("generate")
@click.option(
    "--url",
    default=DEFAULT_SQUARE_GATEWAY_URL,
    help="Gateway webhook URL",
    show_default=True,
)
@click.option(
    "--signature-key",
    default=DEFAULT_SQUARE_SIGNATURE_KEY,
    help="Square webhook signature key",
)
@click.option(
    "--notification-url",
    default=DEFAULT_SQUARE_NOTIFICATION_URL,
    help="Notification URL for signature verification",
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
    "--invalid-signature-rate",
    default=0.0,
    help="Probability of sending invalid signatures (for DLQ testing)",
    show_default=True,
)
def square_generate(
    url: str,
    signature_key: str,
    notification_url: str,
    rate: float,
    duration: int,
    invalid_signature_rate: float,
):
    """Generate continuous Square webhook traffic."""
    click.echo("Starting Square traffic generation:")
    click.echo(f"  URL: {url}")
    click.echo(f"  Rate: {rate} events/sec")
    click.echo(f"  Duration: {duration} seconds")
    click.echo(f"  Expected events: {int(rate * duration)}")
    click.echo(f"  Invalid signature rate: {invalid_signature_rate * 100}%")
    click.echo()

    simulator = SquareWebhookSimulator(
        gateway_url=url,
        signature_key=signature_key,
        notification_url=notification_url,
    )

    async def run():
        stats = await simulator.generate_traffic(
            events_per_second=rate,
            duration_seconds=duration,
            invalid_signature_rate=invalid_signature_rate,
        )
        click.echo()
        click.echo("Results:")
        click.echo(f"  Total sent: {stats['sent']}")
        click.echo(f"  Successful: {stats['success']}")
        click.echo(f"  Failed: {stats['failed']}")
        click.echo(f"  DLQ tests: {stats['dlq_test']}")

    asyncio.run(run())


@square.command("list-events")
def square_list_events():
    """List all available Square event types."""
    click.echo("Available Square event types:")
    click.echo()
    for event_type in AVAILABLE_SQUARE_EVENT_TYPES:
        click.echo(f"  - {event_type}")


@square.command("preview")
@click.option(
    "--type",
    "event_type",
    default="payment.completed",
    help="Event type to preview",
)
@click.option(
    "--signature-key",
    default=DEFAULT_SQUARE_SIGNATURE_KEY,
    help="Webhook signature key (for signature preview)",
)
@click.option(
    "--notification-url",
    default=DEFAULT_SQUARE_NOTIFICATION_URL,
    help="Notification URL for signature generation",
)
def square_preview(event_type: str, signature_key: str, notification_url: str):
    """Preview a generated Square webhook event (without sending)."""
    import json

    simulator = SquareWebhookSimulator(
        gateway_url="http://example.com",
        signature_key=signature_key,
        notification_url=notification_url,
    )

    try:
        event = simulator.generate_event(event_type)
        payload = json.dumps(event, indent=2)
        signature = simulator.sign_payload(payload.encode())

        click.echo("Generated Square Event:")
        click.echo(payload)
        click.echo()
        click.echo(f"x-square-hmacsha256-signature: {signature}")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Adyen Commands
# =============================================================================

AVAILABLE_ADYEN_EVENT_CODES = [
    "AUTHORISATION",
    "CAPTURE",
    "CANCELLATION",
    "REFUND",
    "CHARGEBACK",
    "PENDING",
]


@cli.group()
def adyen():
    """Adyen webhook commands."""
    pass


@adyen.command("send")
@click.option(
    "--url",
    default=DEFAULT_ADYEN_GATEWAY_URL,
    help="Gateway webhook URL",
    show_default=True,
)
@click.option(
    "--hmac-key",
    default=DEFAULT_ADYEN_HMAC_KEY,
    help="Adyen HMAC key (hex-encoded)",
)
@click.option(
    "--event-code",
    default="AUTHORISATION",
    help="Event code to send",
    show_default=True,
)
@click.option(
    "--success/--failure",
    default=True,
    help="Whether the event represents success or failure",
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
def adyen_send(
    url: str,
    hmac_key: str,
    event_code: str,
    success: bool,
    invalid_signature: bool,
    count: int,
):
    """Send one or more Adyen webhook notifications to the gateway."""
    if event_code not in AVAILABLE_ADYEN_EVENT_CODES:
        click.echo(f"Warning: '{event_code}' is not in the known event codes list.")
        click.echo(f"Available codes: {', '.join(AVAILABLE_ADYEN_EVENT_CODES)}")
        if not click.confirm("Continue anyway?"):
            sys.exit(1)

    simulator = AdyenWebhookSimulator(
        gateway_url=url,
        hmac_key=hmac_key,
    )

    async def run():
        for i in range(count):
            click.echo(f"Sending Adyen event {i + 1}/{count}: {event_code} (success={success})")
            try:
                response = await simulator.send_webhook(
                    event_code=event_code,
                    success=success,
                    invalid_signature=invalid_signature,
                )
                click.echo(f"  HTTP Status: {response.status_code}")
                click.echo(f"  Response: {response.text}")
                if response.text == "[accepted]":
                    click.echo("  Result: Accepted by gateway")
            except Exception as e:
                click.echo(f"  Error: {e}", err=True)

    asyncio.run(run())


@adyen.command("generate")
@click.option(
    "--url",
    default=DEFAULT_ADYEN_GATEWAY_URL,
    help="Gateway webhook URL",
    show_default=True,
)
@click.option(
    "--hmac-key",
    default=DEFAULT_ADYEN_HMAC_KEY,
    help="Adyen HMAC key (hex-encoded)",
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
    help="Probability of generating failed events",
    show_default=True,
)
@click.option(
    "--invalid-signature-rate",
    default=0.0,
    help="Probability of sending invalid signatures (for DLQ testing)",
    show_default=True,
)
def adyen_generate(
    url: str,
    hmac_key: str,
    rate: float,
    duration: int,
    failure_rate: float,
    invalid_signature_rate: float,
):
    """Generate continuous Adyen webhook traffic."""
    click.echo("Starting Adyen traffic generation:")
    click.echo(f"  URL: {url}")
    click.echo(f"  Rate: {rate} events/sec")
    click.echo(f"  Duration: {duration} seconds")
    click.echo(f"  Expected events: {int(rate * duration)}")
    click.echo(f"  Failure rate: {failure_rate * 100}%")
    click.echo(f"  Invalid signature rate: {invalid_signature_rate * 100}%")
    click.echo()

    simulator = AdyenWebhookSimulator(
        gateway_url=url,
        hmac_key=hmac_key,
    )

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


@adyen.command("list-events")
def adyen_list_events():
    """List all available Adyen event codes."""
    click.echo("Available Adyen event codes:")
    click.echo()
    for event_code in AVAILABLE_ADYEN_EVENT_CODES:
        click.echo(f"  - {event_code}")


@adyen.command("preview")
@click.option(
    "--event-code",
    default="AUTHORISATION",
    help="Event code to preview",
)
@click.option(
    "--hmac-key",
    default=DEFAULT_ADYEN_HMAC_KEY,
    help="HMAC key (for signature preview)",
)
@click.option(
    "--success/--failure",
    default=True,
    help="Whether the event represents success or failure",
)
def adyen_preview(event_code: str, hmac_key: str, success: bool):
    """Preview a generated Adyen webhook notification (without sending)."""
    import json

    simulator = AdyenWebhookSimulator(
        gateway_url="http://example.com",
        hmac_key=hmac_key,
    )

    try:
        notification = simulator.generate_notification_request(
            event_code=event_code,
            success=success,
            num_items=1,
            sign=True,
        )
        payload = json.dumps(notification, indent=2)

        click.echo("Generated Adyen Notification Request:")
        click.echo(payload)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Braintree Commands
# =============================================================================

AVAILABLE_BRAINTREE_KINDS = [
    "transaction_settled",
    "transaction_settlement_declined",
    "transaction_disbursed",
    "subscription_charged_successfully",
    "subscription_charged_unsuccessfully",
    "subscription_canceled",
    "dispute_opened",
    "dispute_won",
    "dispute_lost",
    "disbursement",
]


@cli.group()
def braintree():
    """Braintree webhook commands."""
    pass


@braintree.command("send")
@click.option(
    "--url",
    default=DEFAULT_BRAINTREE_GATEWAY_URL,
    help="Gateway webhook URL",
    show_default=True,
)
@click.option(
    "--merchant-id",
    default=DEFAULT_BRAINTREE_MERCHANT_ID,
    help="Braintree merchant ID (optional, for SDK mode)",
)
@click.option(
    "--public-key",
    default=DEFAULT_BRAINTREE_PUBLIC_KEY,
    help="Braintree public key (optional, for SDK mode)",
)
@click.option(
    "--private-key",
    default=DEFAULT_BRAINTREE_PRIVATE_KEY,
    help="Braintree private key (optional, for SDK mode)",
)
@click.option(
    "--kind",
    default="transaction_settled",
    help="Notification kind to send",
    show_default=True,
)
@click.option(
    "--use-sdk",
    is_flag=True,
    help="Use Braintree SDK for sample notifications (requires credentials)",
)
@click.option(
    "--count",
    default=1,
    help="Number of events to send",
    show_default=True,
)
def braintree_send(
    url: str,
    merchant_id: str,
    public_key: str,
    private_key: str,
    kind: str,
    use_sdk: bool,
    count: int,
):
    """Send one or more Braintree webhook notifications to the gateway."""
    if kind not in AVAILABLE_BRAINTREE_KINDS:
        click.echo(f"Warning: '{kind}' is not in the known notification kinds list.")
        click.echo(f"Available kinds: {', '.join(AVAILABLE_BRAINTREE_KINDS)}")
        if not click.confirm("Continue anyway?"):
            sys.exit(1)

    if use_sdk and not (merchant_id and public_key and private_key):
        click.echo("Warning: --use-sdk requires merchant-id, public-key, and private-key")
        click.echo("Falling back to mock notifications")
        use_sdk = False

    simulator = BraintreeWebhookSimulator(
        gateway_url=url,
        merchant_id=merchant_id,
        public_key=public_key,
        private_key=private_key,
    )

    async def run():
        for i in range(count):
            click.echo(f"Sending Braintree event {i + 1}/{count}: {kind}")
            try:
                response = await simulator.send_webhook(kind=kind, use_sdk=use_sdk)
                click.echo(f"  HTTP Status: {response.status_code}")
                if response.status_code == 200:
                    result = response.json()
                    click.echo(f"  Status: {result.get('status')}")
                    click.echo(f"  Event ID: {result.get('event_id', 'N/A')}")
                else:
                    click.echo(f"  Response: {response.text[:100]}")
            except Exception as e:
                click.echo(f"  Error: {e}", err=True)

    asyncio.run(run())


@braintree.command("generate")
@click.option(
    "--url",
    default=DEFAULT_BRAINTREE_GATEWAY_URL,
    help="Gateway webhook URL",
    show_default=True,
)
@click.option(
    "--merchant-id",
    default=DEFAULT_BRAINTREE_MERCHANT_ID,
    help="Braintree merchant ID (optional, for SDK mode)",
)
@click.option(
    "--public-key",
    default=DEFAULT_BRAINTREE_PUBLIC_KEY,
    help="Braintree public key (optional, for SDK mode)",
)
@click.option(
    "--private-key",
    default=DEFAULT_BRAINTREE_PRIVATE_KEY,
    help="Braintree private key (optional, for SDK mode)",
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
    "--use-sdk",
    is_flag=True,
    help="Use Braintree SDK for sample notifications (requires credentials)",
)
def braintree_generate(
    url: str,
    merchant_id: str,
    public_key: str,
    private_key: str,
    rate: float,
    duration: int,
    use_sdk: bool,
):
    """Generate continuous Braintree webhook traffic."""
    if use_sdk and not (merchant_id and public_key and private_key):
        click.echo("Warning: --use-sdk requires credentials, falling back to mock")
        use_sdk = False

    click.echo("Starting Braintree traffic generation:")
    click.echo(f"  URL: {url}")
    click.echo(f"  Rate: {rate} events/sec")
    click.echo(f"  Duration: {duration} seconds")
    click.echo(f"  Expected events: {int(rate * duration)}")
    click.echo(f"  SDK mode: {use_sdk}")
    click.echo()

    simulator = BraintreeWebhookSimulator(
        gateway_url=url,
        merchant_id=merchant_id,
        public_key=public_key,
        private_key=private_key,
    )

    async def run():
        stats = await simulator.generate_traffic(
            events_per_second=rate,
            duration_seconds=duration,
            use_sdk=use_sdk,
        )
        click.echo()
        click.echo("Results:")
        click.echo(f"  Total sent: {stats['sent']}")
        click.echo(f"  Successful: {stats['success']}")
        click.echo(f"  Failed: {stats['failed']}")

    asyncio.run(run())


@braintree.command("list-events")
def braintree_list_events():
    """List all available Braintree notification kinds."""
    click.echo("Available Braintree notification kinds:")
    click.echo()
    for kind in AVAILABLE_BRAINTREE_KINDS:
        click.echo(f"  - {kind}")


@braintree.command("preview")
@click.option(
    "--kind",
    default="transaction_settled",
    help="Notification kind to preview",
)
def braintree_preview(kind: str):
    """Preview a generated Braintree webhook notification (without sending)."""
    import json

    simulator = BraintreeWebhookSimulator(gateway_url="http://example.com")

    try:
        notification = simulator.generate_notification(kind=kind, use_sdk=False)

        click.echo("Generated Braintree Notification:")
        click.echo()
        click.echo(f"Kind: {notification['kind']}")
        click.echo(f"SDK Generated: {notification['sdk_generated']}")
        click.echo()
        click.echo("Form Data:")
        click.echo(f"  bt_signature: {notification['bt_signature'][:50]}...")
        click.echo(f"  bt_payload: {notification['bt_payload'][:50]}...")
        click.echo()
        if notification.get("notification_data"):
            click.echo("Decoded Payload:")
            click.echo(json.dumps(notification["notification_data"], indent=2))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
