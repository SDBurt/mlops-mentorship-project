"""Adyen webhook HMAC signature verification.

Adyen standard payment webhooks include the signature in the payload itself,
in additionalData.hmacSignature. The signature is calculated from specific
fields concatenated with colons.

Reference: https://docs.adyen.com/development-resources/webhooks/verify-hmac-signatures
"""

import base64
import hashlib
import hmac
from typing import Any

from payment_gateway.core.exceptions import SignatureVerificationError


def verify_adyen_hmac(
    notification_item: dict[str, Any],
    hmac_key: str,
) -> bool:
    """
    Verify Adyen standard notification HMAC signature.

    The signature is calculated from these fields in order:
    pspReference:originalReference:merchantAccountCode:merchantReference:amount.value:amount.currency:eventCode:success

    Args:
        notification_item: The NotificationRequestItem from the webhook
        hmac_key: HMAC key from Adyen Customer Area (hex string)

    Returns:
        True if signature is valid

    Raises:
        SignatureVerificationError: If signature is invalid or missing
    """
    if not hmac_key:
        # In development mode without a key, skip verification
        return True

    # Get the received signature from additionalData
    additional_data = notification_item.get("additionalData", {}) or {}
    received_signature = additional_data.get("hmacSignature")

    if not received_signature:
        raise SignatureVerificationError("Missing hmacSignature in additionalData")

    # Build the signing string in the EXACT order specified by Adyen
    # Empty fields should be empty strings, not None
    signing_parts = [
        str(notification_item.get("pspReference", "") or ""),
        str(notification_item.get("originalReference", "") or ""),
        str(notification_item.get("merchantAccountCode", "") or ""),
        str(notification_item.get("merchantReference", "") or ""),
        str(notification_item.get("amount", {}).get("value", "") or ""),
        str(notification_item.get("amount", {}).get("currency", "") or ""),
        str(notification_item.get("eventCode", "") or ""),
        str(notification_item.get("success", "")).lower(),  # Must be lowercase "true" or "false"
    ]
    signing_string = ":".join(signing_parts)

    # Convert hex HMAC key to binary
    try:
        binary_key = bytes.fromhex(hmac_key)
    except ValueError as e:
        raise SignatureVerificationError(f"Invalid HMAC key format (must be hex): {e}") from e

    # Calculate expected signature: Base64(HMAC-SHA256(binary_key, signing_string))
    expected_signature = base64.b64encode(
        hmac.new(binary_key, signing_string.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")

    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(received_signature, expected_signature):
        raise SignatureVerificationError("HMAC signature verification failed")

    return True


def generate_adyen_hmac(
    notification_item: dict[str, Any],
    hmac_key: str,
) -> str:
    """
    Generate a valid Adyen HMAC signature for testing.

    Args:
        notification_item: The NotificationRequestItem to sign
        hmac_key: HMAC key (hex string)

    Returns:
        Base64-encoded HMAC signature
    """
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

    binary_key = bytes.fromhex(hmac_key)

    signature = base64.b64encode(
        hmac.new(binary_key, signing_string.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")

    return signature
