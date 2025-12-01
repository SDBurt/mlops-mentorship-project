"""Adyen webhook event generator with signature support."""

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


class AdyenWebhookSimulator:
    """
    Generate and send realistic Adyen webhook notifications.

    Supports:
    - Multiple event codes (AUTHORISATION, CAPTURE, REFUND, etc.)
    - Valid HMAC signature generation (in additionalData.hmacSignature)
    - Configurable success/failure rates
    - Invalid signature generation for DLQ testing
    """

    # Available currencies
    CURRENCIES = ["USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CHF"]

    # Payment methods
    PAYMENT_METHODS = ["visa", "mc", "amex", "discover", "ideal", "paypal", "applepay"]

    # Event codes
    EVENT_CODES = [
        "AUTHORISATION",
        "CAPTURE",
        "CANCELLATION",
        "REFUND",
        "CHARGEBACK",
        "PENDING",
    ]

    # Failure reasons
    FAILURE_REASONS = [
        "Refused",
        "Card Expired",
        "Insufficient Funds",
        "Suspected Fraud",
        "Card Blocked",
        "Invalid Card Number",
    ]

    def __init__(self, gateway_url: str, hmac_key: str):
        """
        Initialize the simulator.

        Args:
            gateway_url: URL of the webhook endpoint
            hmac_key: Adyen HMAC key (hex-encoded, 64 chars for 32 bytes)
        """
        self.gateway_url = gateway_url.rstrip("/") + "/"
        self.hmac_key = hmac_key

    def _generate_psp_reference(self) -> str:
        """Generate an Adyen-style PSP reference (16 digits)."""
        return "".join([str(random.randint(0, 9)) for _ in range(16)])

    def _generate_timestamp(self) -> str:
        """Generate ISO 8601 timestamp with timezone."""
        return datetime.now(timezone.utc).isoformat()

    def _generate_notification_item(
        self,
        event_code: str = "AUTHORISATION",
        success: bool = True,
        amount: int | None = None,
        original_reference: str | None = None,
    ) -> dict[str, Any]:
        """Generate a single Adyen notification item."""
        if amount is None:
            amount = random.randint(100, 100000)  # $1 to $1000 in minor units

        currency = random.choice(self.CURRENCIES)
        psp_reference = self._generate_psp_reference()
        merchant_reference = f"order_{secrets.token_hex(8)}"
        payment_method = random.choice(self.PAYMENT_METHODS)

        item: dict[str, Any] = {
            "pspReference": psp_reference,
            "originalReference": original_reference,
            "merchantAccountCode": "TestMerchantAccount",
            "merchantReference": merchant_reference,
            "amount": {
                "value": amount,
                "currency": currency,
            },
            "eventCode": event_code,
            "success": success,
            "eventDate": self._generate_timestamp(),
            "paymentMethod": payment_method,
            "reason": None if success else random.choice(self.FAILURE_REASONS),
            "operations": [],
            "additionalData": {},
        }

        # Add card details for card payments
        if payment_method in ["visa", "mc", "amex", "discover"]:
            card_bins = {"visa": "411111", "mc": "510000", "amex": "340000", "discover": "601100"}
            item["additionalData"]["cardBin"] = card_bins.get(payment_method, "400000")
            item["additionalData"]["cardSummary"] = str(random.randint(1000, 9999))

        # Add operations for successful authorisation
        if event_code == "AUTHORISATION" and success:
            item["operations"] = ["CAPTURE", "CANCEL"]

        return item

    def generate_hmac_signature(self, notification_item: dict[str, Any]) -> str:
        """
        Generate HMAC signature for a notification item.

        Adyen HMAC format:
        - Fields: pspReference:originalReference:merchantAccountCode:merchantReference:amount.value:amount.currency:eventCode:success
        - Key: hex-decoded HMAC key
        - Algorithm: HMAC-SHA256
        - Output: Base64 encoded

        Args:
            notification_item: The notification item to sign

        Returns:
            Base64-encoded HMAC signature
        """
        # Build signing string with colon separator
        signing_parts = [
            str(notification_item.get("pspReference", "") or ""),
            str(notification_item.get("originalReference", "") or ""),
            str(notification_item.get("merchantAccountCode", "") or ""),
            str(notification_item.get("merchantReference", "") or ""),
            str(notification_item.get("amount", {}).get("value", "") or ""),
            str(notification_item.get("amount", {}).get("currency", "") or ""),
            str(notification_item.get("eventCode", "") or ""),
            str(notification_item.get("success", "")).lower(),
        ]
        signing_string = ":".join(signing_parts)

        # Convert hex key to binary
        binary_key = bytes.fromhex(self.hmac_key)

        # Generate HMAC-SHA256 and base64 encode
        signature = hmac.new(
            binary_key,
            signing_string.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        return base64.b64encode(signature).decode("utf-8")

    def generate_notification_request(
        self,
        event_code: str = "AUTHORISATION",
        success: bool = True,
        num_items: int = 1,
        live: bool = False,
        sign: bool = True,
    ) -> dict[str, Any]:
        """
        Generate a complete Adyen notification request.

        Args:
            event_code: Event code for the notification(s)
            success: Whether the notification represents success
            num_items: Number of notification items to include
            live: Whether this is a live (production) notification
            sign: Whether to include valid HMAC signatures

        Returns:
            Complete Adyen notification request payload
        """
        items = []
        original_ref = None

        for i in range(num_items):
            # For REFUND/CAPTURE, reference the previous AUTHORISATION
            if event_code in ["REFUND", "CAPTURE", "CANCELLATION"] and i == 0:
                # Generate an original authorisation reference
                original_ref = self._generate_psp_reference()

            item = self._generate_notification_item(
                event_code=event_code,
                success=success,
                original_reference=original_ref if event_code != "AUTHORISATION" else None,
            )

            if sign:
                item["additionalData"]["hmacSignature"] = self.generate_hmac_signature(item)

            items.append({"NotificationRequestItem": item})

        return {
            "live": str(live).lower(),
            "notificationItems": items,
        }

    async def send_webhook(
        self,
        event_code: str = "AUTHORISATION",
        success: bool = True,
        num_items: int = 1,
        invalid_signature: bool = False,
    ) -> httpx.Response:
        """
        Send a webhook notification to the gateway.

        Args:
            event_code: Event code to generate
            success: Whether the event represents success
            num_items: Number of items in the batch
            invalid_signature: If True, send with invalid signature (for DLQ testing)

        Returns:
            HTTP response from the gateway
        """
        # Generate notification without signature if we want invalid
        notification = self.generate_notification_request(
            event_code=event_code,
            success=success,
            num_items=num_items,
            sign=not invalid_signature,
        )

        # Add invalid signature if requested
        if invalid_signature:
            for item_wrapper in notification["notificationItems"]:
                item_wrapper["NotificationRequestItem"]["additionalData"]["hmacSignature"] = (
                    "aW52YWxpZF9zaWduYXR1cmU="  # Base64 of "invalid_signature"
                )

        payload = json.dumps(notification).encode("utf-8")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.gateway_url,
                content=payload,
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )

        return response

    async def generate_traffic(
        self,
        events_per_second: float = 1.0,
        duration_seconds: int = 60,
        event_codes: list[str] | None = None,
        failure_rate: float = 0.1,
        invalid_signature_rate: float = 0.0,
    ) -> dict[str, int]:
        """
        Generate continuous webhook traffic.

        Args:
            events_per_second: Rate of event generation
            duration_seconds: How long to generate traffic
            event_codes: List of event codes to generate (defaults to common types)
            failure_rate: Probability of generating failed events
            invalid_signature_rate: Probability of sending invalid signature (for DLQ testing)

        Returns:
            Statistics about generated events
        """
        if event_codes is None:
            event_codes = [
                "AUTHORISATION",
                "CAPTURE",
                "REFUND",
            ]

        stats = {"sent": 0, "success": 0, "failed": 0, "dlq_test": 0}
        interval = 1.0 / events_per_second
        end_time = time.time() + duration_seconds

        logger.info(
            "Starting Adyen traffic generation: %.1f events/sec for %d seconds",
            events_per_second,
            duration_seconds,
        )

        while time.time() < end_time:
            event_code = random.choice(event_codes)

            # Determine if this should be a success or failure
            event_success = random.random() >= failure_rate

            # Determine if this should be a DLQ test (invalid signature)
            invalid_sig = random.random() < invalid_signature_rate

            try:
                response = await self.send_webhook(
                    event_code=event_code,
                    success=event_success,
                    invalid_signature=invalid_sig,
                )
                stats["sent"] += 1

                if invalid_sig:
                    stats["dlq_test"] += 1

                # Adyen expects "[accepted]" response
                if response.status_code == 200 and response.text == "[accepted]":
                    stats["success"] += 1
                    logger.debug("Sent %s (success=%s) -> accepted", event_code, event_success)
                else:
                    stats["failed"] += 1
                    logger.warning(
                        "Unexpected response for %s: HTTP %d, body=%s",
                        event_code,
                        response.status_code,
                        response.text[:100],
                    )

            except Exception as e:
                stats["failed"] += 1
                logger.error("Error sending webhook: %s", str(e))

            await asyncio.sleep(interval)

        logger.info(
            "Adyen traffic generation complete: sent=%d, success=%d, failed=%d, dlq_test=%d",
            stats["sent"],
            stats["success"],
            stats["failed"],
            stats["dlq_test"],
        )

        return stats
