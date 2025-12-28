"""Unit tests for Stripe signature verification."""

import hashlib
import hmac
import time

import pytest

from payment_gateway.core.exceptions import SignatureExpiredError, SignatureVerificationError
from payment_gateway.providers.stripe.validator import (
    generate_stripe_signature,
    verify_stripe_signature,
)


class TestVerifyStripeSignature:
    """Tests for verify_stripe_signature function."""

    def test_valid_signature(self, stripe_webhook_secret):
        """Test that a valid signature passes verification."""
        payload = b'{"test": "data"}'
        timestamp = int(time.time())

        # Generate valid signature
        signed_payload = f"{timestamp}.".encode() + payload
        signature = hmac.new(
            stripe_webhook_secret.encode(),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        signature_header = f"t={timestamp},v1={signature}"

        # Should not raise
        result = verify_stripe_signature(
            payload=payload,
            signature_header=signature_header,
            secret=stripe_webhook_secret,
        )
        assert result is True

    def test_invalid_signature(self, stripe_webhook_secret):
        """Test that an invalid signature is rejected."""
        payload = b'{"test": "data"}'
        timestamp = int(time.time())
        signature_header = f"t={timestamp},v1=invalid_signature_12345"

        with pytest.raises(SignatureVerificationError):
            verify_stripe_signature(
                payload=payload,
                signature_header=signature_header,
                secret=stripe_webhook_secret,
            )

    def test_expired_signature(self, stripe_webhook_secret):
        """Test that an expired signature is rejected."""
        payload = b'{"test": "data"}'
        old_timestamp = int(time.time()) - 600  # 10 minutes ago

        signed_payload = f"{old_timestamp}.".encode() + payload
        signature = hmac.new(
            stripe_webhook_secret.encode(),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        signature_header = f"t={old_timestamp},v1={signature}"

        with pytest.raises(SignatureExpiredError):
            verify_stripe_signature(
                payload=payload,
                signature_header=signature_header,
                secret=stripe_webhook_secret,
                tolerance=300,  # 5 minutes
            )

    def test_missing_timestamp(self, stripe_webhook_secret):
        """Test that missing timestamp is rejected."""
        payload = b'{"test": "data"}'
        signature_header = "v1=some_signature"

        with pytest.raises(SignatureVerificationError) as exc_info:
            verify_stripe_signature(
                payload=payload,
                signature_header=signature_header,
                secret=stripe_webhook_secret,
            )
        assert "timestamp" in str(exc_info.value).lower()

    def test_missing_v1_signature(self, stripe_webhook_secret):
        """Test that missing v1 signature is rejected."""
        payload = b'{"test": "data"}'
        timestamp = int(time.time())
        signature_header = f"t={timestamp}"

        with pytest.raises(SignatureVerificationError) as exc_info:
            verify_stripe_signature(
                payload=payload,
                signature_header=signature_header,
                secret=stripe_webhook_secret,
            )
        assert "v1" in str(exc_info.value).lower()

    def test_empty_secret_skips_verification(self):
        """Test that empty secret skips verification (dev mode)."""
        payload = b'{"test": "data"}'
        signature_header = "t=123,v1=invalid"

        # Should pass without verification when secret is empty
        result = verify_stripe_signature(
            payload=payload,
            signature_header=signature_header,
            secret="",
        )
        assert result is True

    def test_multiple_v1_signatures(self, stripe_webhook_secret):
        """Test that multiple v1 signatures are handled (one valid is enough)."""
        payload = b'{"test": "data"}'
        timestamp = int(time.time())

        # Generate valid signature
        signed_payload = f"{timestamp}.".encode() + payload
        valid_signature = hmac.new(
            stripe_webhook_secret.encode(),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()

        # Include an invalid signature and a valid one
        signature_header = f"t={timestamp},v1=invalid,v1={valid_signature}"

        result = verify_stripe_signature(
            payload=payload,
            signature_header=signature_header,
            secret=stripe_webhook_secret,
        )
        assert result is True

    def test_tampered_payload(self, stripe_webhook_secret):
        """Test that a tampered payload is rejected."""
        original_payload = b'{"amount": 1000}'
        tampered_payload = b'{"amount": 10000}'  # Attacker changed amount
        timestamp = int(time.time())

        # Generate signature for original payload
        signed_payload = f"{timestamp}.".encode() + original_payload
        signature = hmac.new(
            stripe_webhook_secret.encode(),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        signature_header = f"t={timestamp},v1={signature}"

        # Verification with tampered payload should fail
        with pytest.raises(SignatureVerificationError):
            verify_stripe_signature(
                payload=tampered_payload,
                signature_header=signature_header,
                secret=stripe_webhook_secret,
            )


class TestGenerateStripeSignature:
    """Tests for generate_stripe_signature helper function."""

    def test_generate_valid_signature(self, stripe_webhook_secret):
        """Test that generated signatures can be verified."""
        payload = b'{"test": "data"}'
        timestamp = int(time.time())

        signature_header = generate_stripe_signature(
            payload=payload,
            secret=stripe_webhook_secret,
            timestamp=timestamp,
        )

        # Should be able to verify the generated signature
        result = verify_stripe_signature(
            payload=payload,
            signature_header=signature_header,
            secret=stripe_webhook_secret,
        )
        assert result is True

    def test_signature_format(self, stripe_webhook_secret):
        """Test that generated signature has correct format."""
        payload = b'{"test": "data"}'
        timestamp = 1700000000

        signature_header = generate_stripe_signature(
            payload=payload,
            secret=stripe_webhook_secret,
            timestamp=timestamp,
        )

        assert signature_header.startswith("t=1700000000,v1=")
        assert len(signature_header.split(",")) == 2
