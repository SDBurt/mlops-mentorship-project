"""Braintree webhook event generator with SDK support."""

import asyncio
import base64
import json
import logging
import random
import secrets
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class BraintreeWebhookSimulator:
    """
    Generate and send realistic Braintree webhook notifications.

    Supports:
    - Multiple notification kinds (transaction_*, subscription_*, dispute_*)
    - Sample notification generation via Braintree SDK (when credentials provided)
    - Mock notification generation (when no credentials)
    - Configurable event rates
    """

    # Available currencies
    CURRENCIES = ["USD", "CAD", "AUD", "GBP", "EUR"]

    # Payment instrument types
    PAYMENT_INSTRUMENT_TYPES = [
        "credit_card",
        "paypal_account",
        "venmo_account",
        "apple_pay_card",
    ]

    # Card types
    CARD_TYPES = ["Visa", "MasterCard", "American Express", "Discover"]

    # Transaction statuses
    TRANSACTION_STATUSES = [
        "authorized",
        "submitted_for_settlement",
        "settling",
        "settled",
    ]

    # Notification kinds
    NOTIFICATION_KINDS = [
        "transaction_settled",
        "transaction_settlement_declined",
        "subscription_charged_successfully",
        "subscription_charged_unsuccessfully",
        "subscription_canceled",
        "dispute_opened",
        "disbursement",
    ]

    def __init__(
        self,
        gateway_url: str,
        merchant_id: str = "",
        public_key: str = "",
        private_key: str = "",
    ):
        """
        Initialize the simulator.

        Args:
            gateway_url: URL of the webhook endpoint
            merchant_id: Braintree merchant ID (optional, for SDK-based generation)
            public_key: Braintree public key (optional)
            private_key: Braintree private key (optional)
        """
        self.gateway_url = gateway_url.rstrip("/") + "/"
        self.merchant_id = merchant_id
        self.public_key = public_key
        self.private_key = private_key
        self._gateway = None

        # Initialize Braintree gateway if credentials provided
        if merchant_id and public_key and private_key:
            try:
                import braintree
                self._gateway = braintree.BraintreeGateway(
                    braintree.Configuration(
                        environment=braintree.Environment.Sandbox,
                        merchant_id=merchant_id,
                        public_key=public_key,
                        private_key=private_key,
                    )
                )
            except Exception as e:
                logger.warning("Failed to initialize Braintree gateway: %s", e)

    def _generate_id(self, prefix: str = "", length: int = 10) -> str:
        """Generate a random ID."""
        return f"{prefix}{secrets.token_hex(length // 2)}"

    def _generate_timestamp(self) -> str:
        """Generate ISO 8601 timestamp."""
        return datetime.now(timezone.utc).isoformat()

    def _generate_amount(self) -> str:
        """Generate a random amount as decimal string."""
        amount = Decimal(random.randint(100, 100000)) / 100
        return str(amount)

    def _generate_transaction_data(self, status: str = "settled") -> dict[str, Any]:
        """Generate realistic Braintree transaction data."""
        currency = random.choice(self.CURRENCIES)
        payment_type = random.choice(self.PAYMENT_INSTRUMENT_TYPES)

        data: dict[str, Any] = {
            "id": self._generate_id("txn_"),
            "status": status,
            "type": random.choice(["sale", "credit"]),
            "amount": self._generate_amount(),
            "currency_iso_code": currency,
            "merchant_account_id": self._generate_id("merchant_"),
            "customer_id": self._generate_id("customer_") if random.random() > 0.3 else None,
            "payment_instrument_type": payment_type,
        }

        # Add card details for credit card transactions
        if payment_type == "credit_card":
            data["card_details"] = {
                "card_type": random.choice(self.CARD_TYPES),
                "last_4": str(random.randint(1000, 9999)),
            }

        return data

    def _generate_subscription_data(self) -> dict[str, Any]:
        """Generate realistic Braintree subscription data."""
        return {
            "id": self._generate_id("sub_"),
            "status": random.choice(["active", "past_due", "canceled"]),
            "plan_id": random.choice(["monthly_basic", "monthly_pro", "annual"]),
        }

    def _generate_dispute_data(self) -> dict[str, Any]:
        """Generate realistic Braintree dispute data."""
        return {
            "id": self._generate_id("dispute_"),
            "status": random.choice(["open", "won", "lost", "accepted"]),
            "reason": random.choice(["fraud", "duplicate", "not_recognized", "unauthorized"]),
            "amount": self._generate_amount(),
        }

    def generate_notification(
        self,
        kind: str = "transaction_settled",
        use_sdk: bool = False,
    ) -> dict[str, Any]:
        """
        Generate a Braintree notification payload.

        Args:
            kind: Notification kind (e.g., "transaction_settled")
            use_sdk: If True and credentials configured, use SDK sample notifications

        Returns:
            Dictionary with notification data (ready to be sent as form data)
        """
        # If SDK is available and requested, use it for sample notifications
        if use_sdk and self._gateway:
            try:
                bt_signature, bt_payload = self._gateway.webhook_testing.sample_notification(
                    kind, self._generate_id("txn_")
                )
                return {
                    "bt_signature": bt_signature,
                    "bt_payload": bt_payload,
                    "kind": kind,
                    "sdk_generated": True,
                }
            except Exception as e:
                logger.warning("SDK notification generation failed, using mock: %s", e)

        # Generate mock notification
        notification_data = self._generate_mock_notification(kind)

        # Encode as base64 (simulating Braintree's format)
        payload_json = json.dumps(notification_data)
        bt_payload = base64.b64encode(payload_json.encode("utf-8")).decode("utf-8")

        # Generate a mock signature (won't verify, but works for dev mode)
        bt_signature = f"mock_signature|{secrets.token_hex(16)}"

        return {
            "bt_signature": bt_signature,
            "bt_payload": bt_payload,
            "kind": kind,
            "sdk_generated": False,
            "notification_data": notification_data,  # For debugging
        }

    def _generate_mock_notification(self, kind: str) -> dict[str, Any]:
        """Generate mock notification data."""
        notification: dict[str, Any] = {
            "kind": kind,
            "timestamp": self._generate_timestamp(),
        }

        # Add appropriate data based on kind
        if kind.startswith("transaction_"):
            status = "settled" if kind == "transaction_settled" else "failed"
            notification["transaction"] = self._generate_transaction_data(status=status)

        elif kind.startswith("subscription_"):
            notification["subscription"] = self._generate_subscription_data()
            notification["transaction"] = self._generate_transaction_data(
                status="submitted_for_settlement"
            )

        elif kind.startswith("dispute_"):
            notification["dispute"] = self._generate_dispute_data()
            notification["transaction"] = self._generate_transaction_data(status="settled")

        elif kind == "disbursement":
            notification["transaction"] = self._generate_transaction_data(status="settled")

        return notification

    async def send_webhook(
        self,
        kind: str = "transaction_settled",
        use_sdk: bool = False,
    ) -> httpx.Response:
        """
        Send a webhook notification to the gateway.

        Args:
            kind: Notification kind to generate and send
            use_sdk: If True, use SDK to generate sample notifications

        Returns:
            HTTP response from the gateway
        """
        notification = self.generate_notification(kind=kind, use_sdk=use_sdk)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.gateway_url,
                data={
                    "bt_signature": notification["bt_signature"],
                    "bt_payload": notification["bt_payload"],
                },
                timeout=30.0,
            )

        return response

    async def generate_traffic(
        self,
        events_per_second: float = 1.0,
        duration_seconds: int = 60,
        kinds: list[str] | None = None,
        use_sdk: bool = False,
    ) -> dict[str, int]:
        """
        Generate continuous webhook traffic.

        Args:
            events_per_second: Rate of event generation
            duration_seconds: How long to generate traffic
            kinds: List of notification kinds to generate (defaults to common types)
            use_sdk: If True, use SDK for sample notifications

        Returns:
            Statistics about generated events
        """
        if kinds is None:
            kinds = [
                "transaction_settled",
                "subscription_charged_successfully",
                "dispute_opened",
            ]

        stats = {"sent": 0, "success": 0, "failed": 0}
        interval = 1.0 / events_per_second
        end_time = time.time() + duration_seconds

        logger.info(
            "Starting Braintree traffic generation: %.1f events/sec for %d seconds",
            events_per_second,
            duration_seconds,
        )

        while time.time() < end_time:
            kind = random.choice(kinds)

            try:
                response = await self.send_webhook(kind=kind, use_sdk=use_sdk)
                stats["sent"] += 1

                if response.status_code == 200:
                    stats["success"] += 1
                    result = response.json()
                    logger.debug(
                        "Sent %s -> %s (event_id=%s)",
                        kind,
                        result.get("status"),
                        result.get("event_id"),
                    )
                else:
                    stats["failed"] += 1
                    logger.warning(
                        "Failed to send %s: HTTP %d", kind, response.status_code
                    )

            except Exception as e:
                stats["failed"] += 1
                logger.error("Error sending webhook: %s", str(e))

            await asyncio.sleep(interval)

        logger.info(
            "Braintree traffic generation complete: sent=%d, success=%d, failed=%d",
            stats["sent"],
            stats["success"],
            stats["failed"],
        )

        return stats
