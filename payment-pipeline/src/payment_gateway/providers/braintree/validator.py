"""Braintree webhook signature verification using the official SDK."""

import logging
import os
from typing import Any

import braintree

from payment_gateway.core.exceptions import SignatureVerificationError

logger = logging.getLogger(__name__)


def _is_dev_mode() -> bool:
    """
    Check if dev mode is enabled via environment variable.

    Dev mode skips signature verification - NEVER enable in production.
    Requires explicit BRAINTREE_DEV_MODE=true environment variable.
    """
    return os.getenv("BRAINTREE_DEV_MODE", "").lower() == "true"


def get_braintree_gateway(
    merchant_id: str,
    public_key: str,
    private_key: str,
    environment: str = "sandbox",
) -> braintree.BraintreeGateway:
    """
    Create a Braintree gateway instance.

    Args:
        merchant_id: Braintree merchant ID
        public_key: Braintree public key
        private_key: Braintree private key
        environment: "sandbox" or "production"

    Returns:
        Configured BraintreeGateway instance
    """
    env = braintree.Environment.Sandbox
    if environment.lower() == "production":
        env = braintree.Environment.Production

    return braintree.BraintreeGateway(
        braintree.Configuration(
            environment=env,
            merchant_id=merchant_id,
            public_key=public_key,
            private_key=private_key,
        )
    )


def verify_braintree_signature(
    bt_signature: str,
    bt_payload: str,
    gateway: braintree.BraintreeGateway | None = None,
    merchant_id: str = "",
    public_key: str = "",
    private_key: str = "",
) -> bool:
    """
    Verify Braintree webhook signature.

    Braintree webhooks come with two form fields:
    - bt_signature: The signature for verification
    - bt_payload: The base64-encoded notification payload

    Args:
        bt_signature: The bt_signature field from the webhook
        bt_payload: The bt_payload field from the webhook
        gateway: Optional pre-configured gateway instance
        merchant_id: Braintree merchant ID (if gateway not provided)
        public_key: Braintree public key (if gateway not provided)
        private_key: Braintree private key (if gateway not provided)

    Returns:
        True if signature is valid

    Raises:
        SignatureVerificationError: If verification fails
    """
    # Skip verification only if explicitly in dev mode
    if _is_dev_mode():
        logger.warning(
            "BRAINTREE_DEV_MODE=true - Skipping signature verification. "
            "NEVER enable in production!"
        )
        return True

    # Fail-fast if credentials are missing (prevents silent security bypass)
    if not gateway and not (merchant_id and public_key and private_key):
        raise SignatureVerificationError(
            "Braintree credentials not configured. Set merchant_id, public_key, "
            "and private_key, or set BRAINTREE_DEV_MODE=true for local development."
        )

    if not bt_signature:
        raise SignatureVerificationError("Missing bt_signature field")

    if not bt_payload:
        raise SignatureVerificationError("Missing bt_payload field")

    try:
        # Create gateway if not provided
        if not gateway:
            gateway = get_braintree_gateway(merchant_id, public_key, private_key)

        # Parse the webhook - this verifies the signature
        gateway.webhook_notification.parse(bt_signature, bt_payload)
        return True

    except braintree.exceptions.InvalidSignatureError as e:
        raise SignatureVerificationError(f"Invalid Braintree signature: {e}")
    except braintree.exceptions.InvalidChallengeError as e:
        raise SignatureVerificationError(f"Invalid Braintree challenge: {e}")
    except Exception as e:
        raise SignatureVerificationError(f"Braintree verification failed: {e}")


def parse_braintree_webhook(
    bt_signature: str,
    bt_payload: str,
    gateway: braintree.BraintreeGateway | None = None,
    merchant_id: str = "",
    public_key: str = "",
    private_key: str = "",
) -> dict[str, Any]:
    """
    Parse and verify a Braintree webhook notification.

    Args:
        bt_signature: The bt_signature field from the webhook
        bt_payload: The bt_payload field from the webhook
        gateway: Optional pre-configured gateway instance
        merchant_id: Braintree merchant ID (if gateway not provided)
        public_key: Braintree public key (if gateway not provided)
        private_key: Braintree private key (if gateway not provided)

    Returns:
        Dictionary with parsed notification data

    Raises:
        SignatureVerificationError: If verification fails
    """
    # Skip verification only if explicitly in dev mode
    if _is_dev_mode():
        logger.warning(
            "BRAINTREE_DEV_MODE=true - Skipping signature verification. "
            "NEVER enable in production!"
        )
        # For dev mode, decode the payload manually
        import base64
        import json
        import xml.etree.ElementTree as ET

        try:
            decoded = base64.b64decode(bt_payload)
            decoded_str = decoded.decode("utf-8")

            # Try JSON first (simulator format)
            try:
                data = json.loads(decoded_str)
                return {
                    "kind": data.get("kind", "unknown"),
                    "timestamp": data.get("timestamp"),
                    "transaction": data.get("transaction"),
                    "subscription": data.get("subscription"),
                    "dispute": data.get("dispute"),
                    "raw_payload": bt_payload,
                    "dev_mode": True,
                }
            except json.JSONDecodeError:
                pass

            # Fall back to XML (Braintree SDK format)
            root = ET.fromstring(decoded)
            kind = root.find(".//kind")
            timestamp = root.find(".//timestamp")
            return {
                "kind": kind.text if kind is not None else "unknown",
                "timestamp": timestamp.text if timestamp is not None else None,
                "raw_payload": bt_payload,
                "dev_mode": True,
            }
        except Exception:
            return {
                "kind": "unknown",
                "timestamp": None,
                "raw_payload": bt_payload,
                "dev_mode": True,
            }

    # Fail-fast if credentials are missing (prevents silent security bypass)
    if not gateway and not (merchant_id and public_key and private_key):
        raise SignatureVerificationError(
            "Braintree credentials not configured. Set merchant_id, public_key, "
            "and private_key, or set BRAINTREE_DEV_MODE=true for local development."
        )

    try:
        # Create gateway if not provided
        if not gateway:
            gateway = get_braintree_gateway(merchant_id, public_key, private_key)

        # Parse the webhook - this verifies the signature and returns notification
        notification = gateway.webhook_notification.parse(bt_signature, bt_payload)

        # Extract relevant data based on notification kind
        result = {
            "kind": notification.kind,
            "timestamp": notification.timestamp.isoformat() if notification.timestamp else None,
        }

        # Add transaction data if present
        if hasattr(notification, "transaction") and notification.transaction:
            txn = notification.transaction
            result["transaction"] = {
                "id": txn.id,
                "status": txn.status,
                "type": txn.type,
                "amount": str(txn.amount) if txn.amount else None,
                "currency_iso_code": getattr(txn, "currency_iso_code", "USD"),
                "merchant_account_id": txn.merchant_account_id,
                "customer_id": txn.customer_id if hasattr(txn, "customer_id") else None,
                "payment_instrument_type": txn.payment_instrument_type if hasattr(txn, "payment_instrument_type") else None,
            }

            # Add card details if present
            if hasattr(txn, "credit_card_details") and txn.credit_card_details:
                card = txn.credit_card_details
                result["transaction"]["card_details"] = {
                    "card_type": card.card_type if hasattr(card, "card_type") else None,
                    "last_4": card.last_4 if hasattr(card, "last_4") else None,
                }

        # Add subscription data if present
        if hasattr(notification, "subscription") and notification.subscription:
            sub = notification.subscription
            result["subscription"] = {
                "id": sub.id,
                "status": sub.status if hasattr(sub, "status") else None,
                "plan_id": sub.plan_id if hasattr(sub, "plan_id") else None,
            }

        # Add dispute data if present
        if hasattr(notification, "dispute") and notification.dispute:
            dispute = notification.dispute
            result["dispute"] = {
                "id": dispute.id,
                "status": dispute.status if hasattr(dispute, "status") else None,
                "reason": dispute.reason if hasattr(dispute, "reason") else None,
                "amount": str(dispute.amount) if hasattr(dispute, "amount") and dispute.amount else None,
            }

        return result

    except braintree.exceptions.InvalidSignatureError as e:
        raise SignatureVerificationError(f"Invalid Braintree signature: {e}")
    except braintree.exceptions.InvalidChallengeError as e:
        raise SignatureVerificationError(f"Invalid Braintree challenge: {e}")
    except Exception as e:
        raise SignatureVerificationError(f"Braintree parsing failed: {e}")


def generate_sample_notification(
    gateway: braintree.BraintreeGateway,
    kind: str,
    transaction_id: str | None = None,
) -> tuple[str, str]:
    """
    Generate a sample webhook notification for testing.

    This uses Braintree's built-in sample notification generator.

    Args:
        gateway: Configured BraintreeGateway instance
        kind: Notification kind (e.g., "transaction_settled")
        transaction_id: Optional transaction ID

    Returns:
        Tuple of (bt_signature, bt_payload)
    """
    if transaction_id:
        return gateway.webhook_testing.sample_notification(kind, transaction_id)
    return gateway.webhook_testing.sample_notification(kind)
