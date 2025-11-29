"""Stripe webhook signature verification using HMAC-SHA256."""

import hashlib
import hmac
import time

from payment_gateway.core.exceptions import SignatureExpiredError, SignatureVerificationError


def verify_stripe_signature(
    payload: bytes,
    signature_header: str,
    secret: str,
    tolerance: int = 300,
) -> bool:
    """
    Verify Stripe webhook signature using HMAC-SHA256.

    Stripe-Signature header format: t=timestamp,v1=signature,v1=signature2,...

    The signed payload is constructed as: "{timestamp}.{payload}"
    The expected signature is HMAC-SHA256(secret, signed_payload)

    Args:
        payload: Raw request body bytes
        signature_header: Value of Stripe-Signature header
        secret: Webhook signing secret (starts with whsec_)
        tolerance: Maximum age of signature in seconds (default 300 = 5 minutes)

    Returns:
        True if signature is valid

    Raises:
        SignatureVerificationError: If signature is invalid
        SignatureExpiredError: If signature timestamp is too old
    """
    if not secret:
        # In development mode without a secret, skip verification
        return True

    if not signature_header:
        raise SignatureVerificationError("Missing Stripe-Signature header")

    # Parse the signature header
    try:
        elements = {}
        for item in signature_header.split(","):
            key, value = item.split("=", 1)
            if key in elements:
                # Handle multiple v1 signatures
                if isinstance(elements[key], list):
                    elements[key].append(value)
                else:
                    elements[key] = [elements[key], value]
            else:
                elements[key] = value
    except ValueError as e:
        raise SignatureVerificationError(f"Invalid signature header format: {e}") from e

    # Extract timestamp
    timestamp_str = elements.get("t")
    if not timestamp_str:
        raise SignatureVerificationError("Missing timestamp in signature header")

    try:
        timestamp = int(timestamp_str)
    except ValueError as e:
        raise SignatureVerificationError(f"Invalid timestamp format: {e}") from e

    # Check timestamp is within tolerance
    current_time = int(time.time())
    if abs(current_time - timestamp) > tolerance:
        raise SignatureExpiredError(
            f"Signature timestamp ({timestamp}) is outside tolerance window "
            f"({tolerance} seconds). Current time: {current_time}"
        )

    # Get all v1 signatures
    v1_signatures = elements.get("v1")
    if not v1_signatures:
        raise SignatureVerificationError("No v1 signature found in header")

    # Ensure v1_signatures is a list
    if isinstance(v1_signatures, str):
        v1_signatures = [v1_signatures]

    # Compute expected signature
    signed_payload = f"{timestamp}.".encode() + payload
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()

    # Compare signatures using constant-time comparison
    for signature in v1_signatures:
        if hmac.compare_digest(signature, expected_signature):
            return True

    raise SignatureVerificationError("Signature verification failed")


def generate_stripe_signature(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    """
    Generate a valid Stripe webhook signature for testing.

    Args:
        payload: Request body bytes
        secret: Webhook signing secret
        timestamp: Unix timestamp (defaults to current time)

    Returns:
        Stripe-Signature header value
    """
    if timestamp is None:
        timestamp = int(time.time())

    signed_payload = f"{timestamp}.".encode() + payload
    signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()

    return f"t={timestamp},v1={signature}"
