"""Square webhook signature verification using HMAC-SHA256."""

import base64
import hashlib
import hmac

from payment_gateway.core.exceptions import SignatureVerificationError


def verify_square_signature(
    payload: bytes,
    signature_header: str,
    signature_key: str,
    notification_url: str,
) -> bool:
    """
    Verify Square webhook signature using HMAC-SHA256.

    Square signature = Base64(HMAC-SHA256(signature_key, notification_url + raw_body))

    Args:
        payload: Raw request body bytes
        signature_header: Value of x-square-hmacsha256-signature header
        signature_key: Webhook signature key from Square Developer Dashboard
        notification_url: The webhook notification URL configured in Square

    Returns:
        True if signature is valid

    Raises:
        SignatureVerificationError: If signature is invalid or missing
    """
    if not signature_key:
        # In development mode without a secret, skip verification
        return True

    if not signature_header:
        raise SignatureVerificationError("Missing x-square-hmacsha256-signature header")

    if not notification_url:
        raise SignatureVerificationError(
            "Notification URL is required for Square signature verification"
        )

    # Square signature is: HMAC-SHA256(signature_key, notification_url + raw_body)
    # Then base64 encoded
    signed_payload = notification_url.encode("utf-8") + payload

    expected_signature = hmac.new(
        signature_key.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).digest()

    # Square uses base64 encoding for the signature
    expected_b64 = base64.b64encode(expected_signature).decode("utf-8")

    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(signature_header, expected_b64):
        raise SignatureVerificationError("Signature verification failed")

    return True


def generate_square_signature(
    payload: bytes,
    signature_key: str,
    notification_url: str,
) -> str:
    """
    Generate a valid Square webhook signature for testing.

    Args:
        payload: Request body bytes
        signature_key: Webhook signature key
        notification_url: Webhook notification URL

    Returns:
        x-square-hmacsha256-signature header value
    """
    signed_payload = notification_url.encode("utf-8") + payload

    signature = hmac.new(
        signature_key.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).digest()

    return base64.b64encode(signature).decode("utf-8")
