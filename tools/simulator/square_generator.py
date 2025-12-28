"""Square webhook event generator with signature support."""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import random
import secrets
import time
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class SquareWebhookSimulator:
    """
    Generate and send realistic Square webhook events.

    Supports:
    - Multiple event types (payment.*, refund.*)
    - Valid HMAC-SHA256 signature generation
    - Configurable event rates
    - Invalid signature generation for DLQ testing
    """

    # Available currencies
    CURRENCIES = ["USD", "CAD", "AUD", "GBP", "EUR", "JPY"]

    # Payment source types
    SOURCE_TYPES = ["CARD", "CASH", "WALLET", "BANK_ACCOUNT"]

    # Card brands
    CARD_BRANDS = ["VISA", "MASTERCARD", "AMERICAN_EXPRESS", "DISCOVER", "JCB"]

    # Payment statuses
    PAYMENT_STATUSES = ["COMPLETED", "APPROVED", "PENDING", "CANCELED", "FAILED"]

    def __init__(self, gateway_url: str, signature_key: str, notification_url: str):
        """
        Initialize the simulator.

        Args:
            gateway_url: URL of the webhook endpoint
            signature_key: Square webhook signature key
            notification_url: Notification URL for signature verification
        """
        self.gateway_url = gateway_url.rstrip("/") + "/"
        self.signature_key = signature_key
        self.notification_url = notification_url

    def _generate_id(self, prefix: str = "", length: int = 24) -> str:
        """Generate a Square-style ID."""
        return f"{prefix}{secrets.token_hex(length // 2).upper()}"

    def _generate_timestamp(self) -> str:
        """Generate ISO 8601 timestamp."""
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _generate_payment_data(
        self, status: str = "COMPLETED", amount: int | None = None
    ) -> dict[str, Any]:
        """Generate realistic Square payment data object."""
        if amount is None:
            amount = random.randint(100, 100000)  # $1 to $1000 in cents

        currency = random.choice(self.CURRENCIES)
        customer_id = self._generate_id("CUS_") if random.random() > 0.3 else None
        timestamp = self._generate_timestamp()

        data: dict[str, Any] = {
            "id": self._generate_id("PAY_"),
            "created_at": timestamp,
            "updated_at": timestamp,
            "amount_money": {
                "amount": amount,
                "currency": currency,
            },
            "total_money": {
                "amount": amount,
                "currency": currency,
            },
            "status": status,
            "source_type": random.choice(self.SOURCE_TYPES),
            "location_id": self._generate_id("LOC_"),
            "order_id": self._generate_id("ORD_") if random.random() > 0.3 else None,
            "customer_id": customer_id,
            "reference_id": self._generate_id("REF_") if random.random() > 0.5 else None,
        }

        # Add card details if source type is CARD
        if data["source_type"] == "CARD":
            data["card_details"] = {
                "card_brand": random.choice(self.CARD_BRANDS),
                "last_4": str(random.randint(1000, 9999)),
                "exp_month": random.randint(1, 12),
                "exp_year": random.randint(2025, 2030),
            }

        return data

    def _generate_refund_data(self, amount: int | None = None) -> dict[str, Any]:
        """Generate realistic Square refund data object."""
        if amount is None:
            amount = random.randint(100, 50000)

        timestamp = self._generate_timestamp()

        return {
            "id": self._generate_id("REF_"),
            "created_at": timestamp,
            "updated_at": timestamp,
            "amount_money": {
                "amount": amount,
                "currency": random.choice(self.CURRENCIES),
            },
            "status": random.choice(["PENDING", "COMPLETED"]),
            "payment_id": self._generate_id("PAY_"),
            "location_id": self._generate_id("LOC_"),
            "reason": random.choice([
                "Customer requested refund",
                "Duplicate charge",
                "Product returned",
                None,
            ]),
        }

    def generate_event(self, event_type: str) -> dict[str, Any]:
        """
        Generate a complete Square webhook event.

        Args:
            event_type: Event type (e.g., "payment.completed")

        Returns:
            Complete event payload matching Square's format
        """
        event_id = self._generate_id("evt_")
        timestamp = self._generate_timestamp()

        # Determine data object based on event type
        if event_type.startswith("payment."):
            status_map = {
                "payment.completed": "COMPLETED",
                "payment.created": "PENDING",
                "payment.updated": "APPROVED",
            }
            status = status_map.get(event_type, "COMPLETED")
            object_type = "payment"
            object_data = self._generate_payment_data(status=status)

        elif event_type.startswith("refund."):
            object_type = "refund"
            object_data = self._generate_refund_data()

        else:
            raise ValueError(f"Unsupported event type: {event_type}")

        return {
            "merchant_id": self._generate_id("MERCHANT_"),
            "type": event_type,
            "event_id": event_id,
            "created_at": timestamp,
            "data": {
                "type": object_type,
                "id": object_data["id"],
                "object": {
                    object_type: object_data,
                },
            },
        }

    def sign_payload(self, payload: bytes) -> str:
        """
        Generate a valid x-square-hmacsha256-signature header.

        Square signature = Base64(HMAC-SHA256(signature_key, notification_url + raw_body))

        Args:
            payload: JSON payload as bytes

        Returns:
            x-square-hmacsha256-signature header value
        """
        signed_payload = self.notification_url.encode("utf-8") + payload
        signature = hmac.new(
            self.signature_key.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).digest()

        return base64.b64encode(signature).decode("utf-8")

    async def send_webhook(
        self,
        event_type: str,
        invalid_signature: bool = False,
    ) -> httpx.Response:
        """
        Send a webhook event to the gateway.

        Args:
            event_type: Event type to generate and send
            invalid_signature: If True, send with an invalid signature (for DLQ testing)

        Returns:
            HTTP response from the gateway
        """
        event = self.generate_event(event_type)
        payload = json.dumps(event).encode("utf-8")

        if invalid_signature:
            signature = "aW52YWxpZF9zaWduYXR1cmU="  # Base64 of "invalid_signature"
        else:
            signature = self.sign_payload(payload)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.gateway_url,
                content=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-square-hmacsha256-signature": signature,
                },
                timeout=30.0,
            )

        return response

    async def generate_traffic(
        self,
        events_per_second: float = 1.0,
        duration_seconds: int = 60,
        event_types: list[str] | None = None,
        failure_rate: float = 0.1,
        invalid_signature_rate: float = 0.0,
    ) -> dict[str, int]:
        """
        Generate continuous webhook traffic.

        Args:
            events_per_second: Rate of event generation
            duration_seconds: How long to generate traffic
            event_types: List of event types to generate (defaults to common types)
            failure_rate: Not used for Square (no explicit failure events)
            invalid_signature_rate: Probability of sending invalid signature (for DLQ testing)

        Returns:
            Statistics about generated events
        """
        if event_types is None:
            event_types = [
                "payment.completed",
                "payment.created",
                "payment.updated",
                "refund.created",
                "refund.updated",
            ]

        stats = {"sent": 0, "success": 0, "failed": 0, "dlq_test": 0}
        interval = 1.0 / events_per_second
        end_time = time.time() + duration_seconds

        logger.info(
            "Starting Square traffic generation: %.1f events/sec for %d seconds",
            events_per_second,
            duration_seconds,
        )

        while time.time() < end_time:
            event_type = random.choice(event_types)

            # Determine if this should be a DLQ test (invalid signature)
            invalid_sig = random.random() < invalid_signature_rate

            try:
                response = await self.send_webhook(event_type, invalid_signature=invalid_sig)
                stats["sent"] += 1

                if invalid_sig:
                    stats["dlq_test"] += 1

                if response.status_code == 200:
                    stats["success"] += 1
                    result = response.json()
                    logger.debug(
                        "Sent %s -> %s (event_id=%s)",
                        event_type,
                        result.get("status"),
                        result.get("event_id"),
                    )
                else:
                    stats["failed"] += 1
                    logger.warning(
                        "Failed to send %s: HTTP %d", event_type, response.status_code
                    )

            except Exception as e:
                stats["failed"] += 1
                logger.error("Error sending webhook: %s", str(e))

            await asyncio.sleep(interval)

        logger.info(
            "Square traffic generation complete: sent=%d, success=%d, failed=%d, dlq_test=%d",
            stats["sent"],
            stats["success"],
            stats["failed"],
            stats["dlq_test"],
        )

        return stats
