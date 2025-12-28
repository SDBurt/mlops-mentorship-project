"""Unit tests for Adyen HMAC signature verification."""

import base64
import hashlib
import hmac

import pytest

from payment_gateway.core.exceptions import SignatureVerificationError
from payment_gateway.providers.adyen.validator import (
    generate_adyen_hmac,
    verify_adyen_hmac,
)


class TestVerifyAdyenHmac:
    """Tests for verify_adyen_hmac function."""

    def test_valid_signature(self, adyen_hmac_key, valid_adyen_notification_item):
        """Test that a valid signature passes verification."""
        # Generate valid signature and add to additionalData
        item = valid_adyen_notification_item.copy()
        item["additionalData"] = item.get("additionalData", {}).copy()
        item["additionalData"]["hmacSignature"] = generate_adyen_hmac(item, adyen_hmac_key)

        # Should not raise
        result = verify_adyen_hmac(
            notification_item=item,
            hmac_key=adyen_hmac_key,
        )
        assert result is True

    def test_invalid_signature(self, adyen_hmac_key, valid_adyen_notification_item):
        """Test that an invalid signature is rejected."""
        item = valid_adyen_notification_item.copy()
        item["additionalData"] = item.get("additionalData", {}).copy()
        item["additionalData"]["hmacSignature"] = "aW52YWxpZF9zaWduYXR1cmU="

        with pytest.raises(SignatureVerificationError):
            verify_adyen_hmac(
                notification_item=item,
                hmac_key=adyen_hmac_key,
            )

    def test_missing_signature(self, adyen_hmac_key, valid_adyen_notification_item):
        """Test that missing signature is rejected."""
        item = valid_adyen_notification_item.copy()
        item["additionalData"] = {}  # No hmacSignature

        with pytest.raises(SignatureVerificationError) as exc_info:
            verify_adyen_hmac(
                notification_item=item,
                hmac_key=adyen_hmac_key,
            )
        assert "missing" in str(exc_info.value).lower()

    def test_empty_key_skips_verification(self, valid_adyen_notification_item):
        """Test that empty HMAC key skips verification (dev mode)."""
        item = valid_adyen_notification_item.copy()
        item["additionalData"] = {"hmacSignature": "any_value"}

        # Should pass without verification when key is empty
        result = verify_adyen_hmac(
            notification_item=item,
            hmac_key="",
        )
        assert result is True

    def test_tampered_amount(self, adyen_hmac_key, valid_adyen_notification_item):
        """Test that a tampered amount is rejected."""
        original_item = valid_adyen_notification_item.copy()
        original_item["additionalData"] = original_item.get("additionalData", {}).copy()
        original_item["additionalData"]["hmacSignature"] = generate_adyen_hmac(
            original_item, adyen_hmac_key
        )

        # Tamper with amount
        tampered_item = original_item.copy()
        tampered_item["amount"] = {"value": 99999, "currency": "USD"}
        tampered_item["additionalData"] = original_item["additionalData"].copy()

        with pytest.raises(SignatureVerificationError):
            verify_adyen_hmac(
                notification_item=tampered_item,
                hmac_key=adyen_hmac_key,
            )

    def test_tampered_psp_reference(self, adyen_hmac_key, valid_adyen_notification_item):
        """Test that a tampered pspReference is rejected."""
        original_item = valid_adyen_notification_item.copy()
        original_item["additionalData"] = original_item.get("additionalData", {}).copy()
        original_item["additionalData"]["hmacSignature"] = generate_adyen_hmac(
            original_item, adyen_hmac_key
        )

        # Tamper with pspReference
        tampered_item = original_item.copy()
        tampered_item["pspReference"] = "FAKE_REFERENCE"
        tampered_item["additionalData"] = original_item["additionalData"].copy()

        with pytest.raises(SignatureVerificationError):
            verify_adyen_hmac(
                notification_item=tampered_item,
                hmac_key=adyen_hmac_key,
            )

    def test_tampered_success_flag(self, adyen_hmac_key, valid_adyen_notification_item):
        """Test that a tampered success flag is rejected."""
        original_item = valid_adyen_notification_item.copy()
        original_item["additionalData"] = original_item.get("additionalData", {}).copy()
        original_item["additionalData"]["hmacSignature"] = generate_adyen_hmac(
            original_item, adyen_hmac_key
        )

        # Tamper with success (True -> False)
        tampered_item = original_item.copy()
        tampered_item["success"] = False
        tampered_item["additionalData"] = original_item["additionalData"].copy()

        with pytest.raises(SignatureVerificationError):
            verify_adyen_hmac(
                notification_item=tampered_item,
                hmac_key=adyen_hmac_key,
            )

    def test_handles_none_values(self, adyen_hmac_key):
        """Test that None values in fields are handled correctly."""
        item = {
            "pspReference": "12345",
            "originalReference": None,
            "merchantAccountCode": "TestMerchant",
            "merchantReference": None,
            "amount": {"value": 1000, "currency": "USD"},
            "eventCode": "AUTHORISATION",
            "success": True,
            "additionalData": {},
        }

        # Generate and verify
        signature = generate_adyen_hmac(item, adyen_hmac_key)
        item["additionalData"]["hmacSignature"] = signature

        result = verify_adyen_hmac(item, adyen_hmac_key)
        assert result is True


class TestGenerateAdyenHmac:
    """Tests for generate_adyen_hmac helper function."""

    def test_generate_valid_signature(self, adyen_hmac_key, valid_adyen_notification_item):
        """Test that generated signatures can be verified."""
        item = valid_adyen_notification_item.copy()
        item["additionalData"] = item.get("additionalData", {}).copy()

        signature = generate_adyen_hmac(item, adyen_hmac_key)
        item["additionalData"]["hmacSignature"] = signature

        # Should be able to verify the generated signature
        result = verify_adyen_hmac(item, adyen_hmac_key)
        assert result is True

    def test_signature_is_base64_encoded(self, adyen_hmac_key, valid_adyen_notification_item):
        """Test that generated signature is valid base64."""
        signature = generate_adyen_hmac(valid_adyen_notification_item, adyen_hmac_key)

        # Should be valid base64
        try:
            decoded = base64.b64decode(signature)
            # SHA256 produces 32 bytes
            assert len(decoded) == 32
        except Exception as e:
            pytest.fail(f"Signature is not valid base64: {e}")

    def test_deterministic_signature(self, adyen_hmac_key, valid_adyen_notification_item):
        """Test that the same input produces the same signature."""
        sig1 = generate_adyen_hmac(valid_adyen_notification_item, adyen_hmac_key)
        sig2 = generate_adyen_hmac(valid_adyen_notification_item, adyen_hmac_key)

        assert sig1 == sig2

    def test_different_items_different_signatures(
        self, adyen_hmac_key, valid_adyen_notification_item, valid_adyen_refund_item
    ):
        """Test that different items produce different signatures."""
        sig1 = generate_adyen_hmac(valid_adyen_notification_item, adyen_hmac_key)
        sig2 = generate_adyen_hmac(valid_adyen_refund_item, adyen_hmac_key)

        assert sig1 != sig2

    def test_signing_string_format(self, adyen_hmac_key, valid_adyen_notification_item):
        """Test that signing string uses colon separator."""
        item = valid_adyen_notification_item
        # Manually construct expected signing string
        parts = [
            item["pspReference"],
            str(item.get("originalReference") or ""),
            item["merchantAccountCode"],
            str(item.get("merchantReference") or ""),
            str(item["amount"]["value"]),
            item["amount"]["currency"],
            item["eventCode"],
            str(item["success"]).lower(),
        ]
        expected_string = ":".join(parts)

        # Compute expected signature
        binary_key = bytes.fromhex(adyen_hmac_key)
        expected_sig = base64.b64encode(
            hmac.new(binary_key, expected_string.encode("utf-8"), hashlib.sha256).digest()
        ).decode("utf-8")

        actual_sig = generate_adyen_hmac(item, adyen_hmac_key)

        assert actual_sig == expected_sig
