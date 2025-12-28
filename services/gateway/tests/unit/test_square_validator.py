"""Unit tests for Square signature verification."""

import base64
import hashlib
import hmac

import pytest

from payment_gateway.core.exceptions import SignatureVerificationError
from payment_gateway.providers.square.validator import (
    generate_square_signature,
    verify_square_signature,
)


class TestVerifySquareSignature:
    """Tests for verify_square_signature function."""

    def test_valid_signature(self, square_signature_key, square_notification_url):
        """Test that a valid signature passes verification."""
        payload = b'{"test": "data"}'

        # Generate valid signature
        signed_payload = square_notification_url.encode("utf-8") + payload
        signature = hmac.new(
            square_signature_key.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).digest()
        signature_header = base64.b64encode(signature).decode("utf-8")

        # Should not raise
        result = verify_square_signature(
            payload=payload,
            signature_header=signature_header,
            signature_key=square_signature_key,
            notification_url=square_notification_url,
        )
        assert result is True

    def test_invalid_signature(self, square_signature_key, square_notification_url):
        """Test that an invalid signature is rejected."""
        payload = b'{"test": "data"}'
        signature_header = "aW52YWxpZF9zaWduYXR1cmU="  # Base64 of "invalid_signature"

        with pytest.raises(SignatureVerificationError):
            verify_square_signature(
                payload=payload,
                signature_header=signature_header,
                signature_key=square_signature_key,
                notification_url=square_notification_url,
            )

    def test_missing_signature_header(self, square_signature_key, square_notification_url):
        """Test that missing signature header is rejected."""
        payload = b'{"test": "data"}'

        with pytest.raises(SignatureVerificationError) as exc_info:
            verify_square_signature(
                payload=payload,
                signature_header="",
                signature_key=square_signature_key,
                notification_url=square_notification_url,
            )
        assert "missing" in str(exc_info.value).lower()

    def test_missing_notification_url(self, square_signature_key):
        """Test that missing notification URL is rejected."""
        payload = b'{"test": "data"}'
        signature_header = "some_signature"

        with pytest.raises(SignatureVerificationError) as exc_info:
            verify_square_signature(
                payload=payload,
                signature_header=signature_header,
                signature_key=square_signature_key,
                notification_url="",
            )
        assert "notification url" in str(exc_info.value).lower()

    def test_empty_secret_skips_verification(self, square_notification_url):
        """Test that empty secret skips verification (dev mode)."""
        payload = b'{"test": "data"}'
        signature_header = "invalid_signature"

        # Should pass without verification when secret is empty
        result = verify_square_signature(
            payload=payload,
            signature_header=signature_header,
            signature_key="",
            notification_url=square_notification_url,
        )
        assert result is True

    def test_tampered_payload(self, square_signature_key, square_notification_url):
        """Test that a tampered payload is rejected."""
        original_payload = b'{"amount": 1000}'
        tampered_payload = b'{"amount": 10000}'  # Attacker changed amount

        # Generate signature for original payload
        signed_payload = square_notification_url.encode("utf-8") + original_payload
        signature = hmac.new(
            square_signature_key.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).digest()
        signature_header = base64.b64encode(signature).decode("utf-8")

        # Verification with tampered payload should fail
        with pytest.raises(SignatureVerificationError):
            verify_square_signature(
                payload=tampered_payload,
                signature_header=signature_header,
                signature_key=square_signature_key,
                notification_url=square_notification_url,
            )

    def test_wrong_notification_url(self, square_signature_key, square_notification_url):
        """Test that wrong notification URL causes verification failure."""
        payload = b'{"test": "data"}'

        # Generate signature with correct URL
        signed_payload = square_notification_url.encode("utf-8") + payload
        signature = hmac.new(
            square_signature_key.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).digest()
        signature_header = base64.b64encode(signature).decode("utf-8")

        # Verification with different URL should fail
        with pytest.raises(SignatureVerificationError):
            verify_square_signature(
                payload=payload,
                signature_header=signature_header,
                signature_key=square_signature_key,
                notification_url="https://wrong-url.com/webhooks/",
            )


class TestGenerateSquareSignature:
    """Tests for generate_square_signature helper function."""

    def test_generate_valid_signature(self, square_signature_key, square_notification_url):
        """Test that generated signatures can be verified."""
        payload = b'{"test": "data"}'

        signature_header = generate_square_signature(
            payload=payload,
            signature_key=square_signature_key,
            notification_url=square_notification_url,
        )

        # Should be able to verify the generated signature
        result = verify_square_signature(
            payload=payload,
            signature_header=signature_header,
            signature_key=square_signature_key,
            notification_url=square_notification_url,
        )
        assert result is True

    def test_signature_is_base64_encoded(self, square_signature_key, square_notification_url):
        """Test that generated signature is valid base64."""
        payload = b'{"test": "data"}'

        signature_header = generate_square_signature(
            payload=payload,
            signature_key=square_signature_key,
            notification_url=square_notification_url,
        )

        # Should be valid base64
        try:
            decoded = base64.b64decode(signature_header)
            # SHA256 produces 32 bytes
            assert len(decoded) == 32
        except Exception as e:
            pytest.fail(f"Signature is not valid base64: {e}")
