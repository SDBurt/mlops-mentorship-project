"""Stripe webhook event generator with signature support."""

import asyncio
import hashlib
import hmac
import json
import logging
import random
import secrets
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class StripeWebhookSimulator:
    """
    Generate and send realistic Stripe webhook events.

    Supports:
    - Multiple event types (payment_intent.*, charge.*, refund.*)
    - Valid HMAC-SHA256 signature generation
    - Configurable event rates
    - Invalid signature generation for DLQ testing
    """

    # Available currencies
    CURRENCIES = ["usd", "eur", "gbp", "cad", "aud", "jpy"]

    # Payment method types
    PAYMENT_METHOD_TYPES = ["card", "us_bank_account", "sepa_debit"]

    # Card brands for payment method details
    CARD_BRANDS = ["visa", "mastercard", "amex", "discover"]

    # Failure codes for failed payments
    FAILURE_CODES = [
        "card_declined",
        "insufficient_funds",
        "expired_card",
        "incorrect_cvc",
        "processing_error",
        "lost_card",
        "stolen_card",
    ]

    def __init__(self, gateway_url: str, webhook_secret: str):
        """
        Initialize the simulator.

        Args:
            gateway_url: URL of the webhook endpoint
            webhook_secret: Stripe webhook signing secret
        """
        self.gateway_url = gateway_url.rstrip("/") + "/"
        self.webhook_secret = webhook_secret

    def _generate_id(self, prefix: str, length: int = 24) -> str:
        """Generate a Stripe-style ID with prefix."""
        return f"{prefix}{secrets.token_hex(length // 2)}"

    def _generate_payment_intent_data(
        self, status: str = "succeeded", amount: int | None = None
    ) -> dict[str, Any]:
        """Generate realistic payment_intent data object."""
        if amount is None:
            amount = random.randint(100, 100000)  # $1 to $1000 in cents

        currency = random.choice(self.CURRENCIES)
        customer_id = self._generate_id("cus_", 14) if random.random() > 0.2 else None
        payment_method_id = self._generate_id("pm_", 24)

        data: dict[str, Any] = {
            "id": self._generate_id("pi_", 24),
            "object": "payment_intent",
            "amount": amount,
            "amount_capturable": 0,
            "amount_received": amount if status == "succeeded" else 0,
            "currency": currency,
            "status": status,
            "customer": customer_id,
            "payment_method": payment_method_id,
            "payment_method_types": [random.choice(self.PAYMENT_METHOD_TYPES)],
            "description": f"Payment for order {self._generate_id('ord_', 10)}",
            "metadata": {
                "order_id": self._generate_id("ord_", 10),
                "customer_email": f"customer{random.randint(1, 1000)}@example.com",
            },
            "created": int(time.time()) - random.randint(0, 3600),
            "livemode": False,
            "last_payment_error": None,
            "cancellation_reason": None,
        }

        if status == "requires_payment_method":
            data["last_payment_error"] = {
                "code": random.choice(self.FAILURE_CODES),
                "message": "Your card was declined.",
                "type": "card_error",
            }

        return data

    def _generate_charge_data(
        self, status: str = "succeeded", amount: int | None = None
    ) -> dict[str, Any]:
        """Generate realistic charge data object."""
        if amount is None:
            amount = random.randint(100, 100000)

        currency = random.choice(self.CURRENCIES)
        paid = status == "succeeded"
        captured = paid

        data: dict[str, Any] = {
            "id": self._generate_id("ch_", 24),
            "object": "charge",
            "amount": amount,
            "amount_captured": amount if captured else 0,
            "amount_refunded": 0,
            "currency": currency,
            "status": status,
            "paid": paid,
            "captured": captured,
            "refunded": False,
            "disputed": False,
            "customer": self._generate_id("cus_", 14) if random.random() > 0.2 else None,
            "payment_intent": self._generate_id("pi_", 24),
            "payment_method": self._generate_id("pm_", 24),
            "payment_method_details": {
                "card": {
                    "brand": random.choice(self.CARD_BRANDS),
                    "last4": str(random.randint(1000, 9999)),
                    "exp_month": random.randint(1, 12),
                    "exp_year": random.randint(2025, 2030),
                    "country": "US",
                }
            },
            "failure_code": None,
            "failure_message": None,
            "description": f"Charge for order {self._generate_id('ord_', 10)}",
            "metadata": {},
            "created": int(time.time()) - random.randint(0, 3600),
            "livemode": False,
        }

        if status == "failed":
            data["failure_code"] = random.choice(self.FAILURE_CODES)
            data["failure_message"] = "Your card was declined."

        return data

    def _generate_refund_data(self, amount: int | None = None) -> dict[str, Any]:
        """Generate realistic refund data object."""
        if amount is None:
            amount = random.randint(100, 50000)

        return {
            "id": self._generate_id("re_", 24),
            "object": "refund",
            "amount": amount,
            "currency": random.choice(self.CURRENCIES),
            "status": "succeeded",
            "charge": self._generate_id("ch_", 24),
            "payment_intent": self._generate_id("pi_", 24),
            "reason": random.choice(["duplicate", "fraudulent", "requested_by_customer", None]),
            "metadata": {},
            "created": int(time.time()),
            "failure_reason": None,
        }

    def generate_event(self, event_type: str) -> dict[str, Any]:
        """
        Generate a complete Stripe webhook event.

        Args:
            event_type: Event type (e.g., "payment_intent.succeeded")

        Returns:
            Complete event payload matching Stripe's format
        """
        event_id = self._generate_id("evt_", 24)
        timestamp = int(time.time())

        # Determine data object based on event type
        if event_type.startswith("payment_intent."):
            status_map = {
                "payment_intent.succeeded": "succeeded",
                "payment_intent.payment_failed": "requires_payment_method",
                "payment_intent.created": "requires_payment_method",
                "payment_intent.canceled": "canceled",
                "payment_intent.processing": "processing",
            }
            status = status_map.get(event_type, "succeeded")
            data_object = self._generate_payment_intent_data(status=status)

        elif event_type.startswith("charge."):
            status_map = {
                "charge.succeeded": "succeeded",
                "charge.failed": "failed",
                "charge.pending": "pending",
                "charge.captured": "succeeded",
                "charge.refunded": "succeeded",
            }
            status = status_map.get(event_type, "succeeded")
            data_object = self._generate_charge_data(status=status)
            if event_type == "charge.refunded":
                data_object["refunded"] = True

        elif event_type.startswith("refund."):
            data_object = self._generate_refund_data()

        else:
            raise ValueError(f"Unsupported event type: {event_type}")

        return {
            "id": event_id,
            "object": "event",
            "api_version": "2024-09-30.acacia",
            "created": timestamp,
            "type": event_type,
            "data": {
                "object": data_object,
                "previous_attributes": None,
            },
            "livemode": False,
            "pending_webhooks": 1,
            "request": {
                "id": self._generate_id("req_", 14),
                "idempotency_key": None,
            },
        }

    def sign_payload(self, payload: bytes, timestamp: int | None = None) -> str:
        """
        Generate a valid Stripe-Signature header.

        Args:
            payload: JSON payload as bytes
            timestamp: Unix timestamp (defaults to current time)

        Returns:
            Stripe-Signature header value
        """
        if timestamp is None:
            timestamp = int(time.time())

        signed_payload = f"{timestamp}.".encode() + payload
        signature = hmac.new(
            self.webhook_secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()

        return f"t={timestamp},v1={signature}"

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
            signature = "t=0,v1=invalid_signature_for_testing"
        else:
            signature = self.sign_payload(payload)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.gateway_url,
                content=payload,
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": signature,
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
            failure_rate: Probability of generating a failed payment event
            invalid_signature_rate: Probability of sending invalid signature (for DLQ testing)

        Returns:
            Statistics about generated events
        """
        if event_types is None:
            event_types = [
                "payment_intent.succeeded",
                "payment_intent.payment_failed",
                "charge.succeeded",
                "charge.failed",
                "refund.created",
            ]

        stats = {"sent": 0, "success": 0, "failed": 0, "dlq_test": 0}
        interval = 1.0 / events_per_second
        end_time = time.time() + duration_seconds

        logger.info(
            "Starting traffic generation: %.1f events/sec for %d seconds",
            events_per_second,
            duration_seconds,
        )

        while time.time() < end_time:
            # Select event type (bias toward failures based on failure_rate)
            if random.random() < failure_rate:
                event_type = random.choice(
                    [et for et in event_types if "failed" in et]
                    or ["payment_intent.payment_failed"]
                )
            else:
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
            "Traffic generation complete: sent=%d, success=%d, failed=%d, dlq_test=%d",
            stats["sent"],
            stats["success"],
            stats["failed"],
            stats["dlq_test"],
        )

        return stats
