"""Unit tests for Adyen event transformer."""

import pytest

from transformer.transformers.adyen import AdyenTransformer


class TestAdyenTransformer:
    """Tests for AdyenTransformer class."""

    @pytest.fixture
    def transformer(self):
        """Create an AdyenTransformer instance."""
        return AdyenTransformer()

    def test_transform_valid_authorisation(self, transformer, valid_adyen_notification_item):
        """Test transforming a valid AUTHORISATION notification."""
        unified_event, result = transformer.transform(valid_adyen_notification_item)

        assert result.is_valid is True
        assert unified_event is not None
        assert unified_event.event_id == "adyen:7914073381342284_AUTHORISATION"
        assert unified_event.provider == "adyen"
        assert unified_event.provider_event_id == "7914073381342284"
        assert unified_event.event_type == "payment.authorized"
        assert unified_event.amount_cents == 2000
        assert unified_event.currency == "USD"
        assert unified_event.status == "authorized"
        assert unified_event.merchant_id == "TestMerchant"
        assert unified_event.card_brand == "411111"  # cardBin
        assert unified_event.card_last_four == "1111"
        assert unified_event.payment_method_type == "card"

    def test_transform_valid_refund(self, transformer, valid_adyen_refund_item):
        """Test transforming a valid REFUND notification."""
        unified_event, result = transformer.transform(valid_adyen_refund_item)

        assert result.is_valid is True
        assert unified_event is not None
        assert unified_event.event_id == "adyen:8814073381342285_REFUND"
        assert unified_event.provider == "adyen"
        assert unified_event.event_type == "refund.created"
        assert unified_event.amount_cents == 1000
        assert unified_event.currency == "USD"
        assert unified_event.status == "refunded"
        assert unified_event.metadata.get("original_reference") == "7914073381342284"

    def test_transform_failed_authorisation(self, transformer, valid_adyen_failed_auth):
        """Test transforming a failed AUTHORISATION notification."""
        unified_event, result = transformer.transform(valid_adyen_failed_auth)

        assert result.is_valid is True
        assert unified_event is not None
        assert unified_event.status == "failed"
        assert unified_event.failure_message == "Refused"
        assert unified_event.failure_code == "declined"
        assert unified_event.currency == "EUR"
        assert unified_event.amount_cents == 5000

    def test_transform_missing_psp_reference(self, transformer, valid_adyen_notification_item):
        """Test that missing pspReference causes validation failure."""
        item = valid_adyen_notification_item.copy()
        del item["pspReference"]

        unified_event, result = transformer.transform(item)

        assert result.is_valid is False
        assert "MISSING_PSP_REFERENCE" in result.error_codes
        assert unified_event is None

    def test_transform_missing_event_code(self, transformer, valid_adyen_notification_item):
        """Test that missing eventCode causes validation failure."""
        item = valid_adyen_notification_item.copy()
        del item["eventCode"]

        unified_event, result = transformer.transform(item)

        assert result.is_valid is False
        assert "MISSING_EVENT_CODE" in result.error_codes

    def test_transform_missing_merchant_account(self, transformer, valid_adyen_notification_item):
        """Test that missing merchantAccountCode causes validation failure."""
        item = valid_adyen_notification_item.copy()
        del item["merchantAccountCode"]

        unified_event, result = transformer.transform(item)

        assert result.is_valid is False
        assert "MISSING_MERCHANT_ACCOUNT" in result.error_codes

    def test_transform_invalid_currency(self, transformer, valid_adyen_notification_item):
        """Test that invalid currency causes validation failure."""
        item = valid_adyen_notification_item.copy()
        item["amount"]["currency"] = "XYZ"

        unified_event, result = transformer.transform(item)

        assert result.is_valid is False
        assert "INVALID_CURRENCY" in result.error_codes
        assert unified_event is None

    def test_transform_negative_amount(self, transformer, valid_adyen_notification_item):
        """Test that negative amount causes validation failure."""
        item = valid_adyen_notification_item.copy()
        item["amount"]["value"] = -100

        unified_event, result = transformer.transform(item)

        assert result.is_valid is False
        assert any("INVALID_AMOUNT" in code for code in result.error_codes)
        assert unified_event is None

    def test_transform_normalizes_payment_method(self, transformer, valid_adyen_notification_item):
        """Test that payment methods are normalized correctly."""
        test_cases = [
            ("visa", "card"),
            ("mc", "card"),
            ("amex", "card"),
            ("ideal", "bank_transfer"),
            ("paypal", "paypal"),
            ("applepay", "wallet"),
            ("googlepay", "wallet"),
            ("klarna", "buy_now_pay_later"),
        ]

        for adyen_method, expected in test_cases:
            item = valid_adyen_notification_item.copy()
            item["paymentMethod"] = adyen_method

            unified_event, result = transformer.transform(item)

            assert result.is_valid is True
            assert unified_event.payment_method_type == expected, (
                f"Expected {expected} for {adyen_method}"
            )

    def test_transform_extracts_metadata(self, transformer, valid_adyen_notification_item):
        """Test that metadata is correctly extracted."""
        unified_event, result = transformer.transform(valid_adyen_notification_item)

        assert result.is_valid is True
        assert unified_event.metadata.get("merchant_reference") == "order_12345"
        assert unified_event.metadata.get("operations") == ["CAPTURE", "CANCEL"]
        assert unified_event.metadata.get("live") is False

    def test_transform_handles_missing_amount(self, transformer, valid_adyen_notification_item):
        """Test handling of events without amount."""
        item = valid_adyen_notification_item.copy()
        del item["amount"]

        unified_event, result = transformer.transform(item)

        # Should fail validation - amount is required
        assert result.is_valid is False
        assert any("INVALID_AMOUNT" in code for code in result.error_codes)

    def test_transform_handles_null_additional_data(self, transformer, valid_adyen_notification_item):
        """Test handling of null additionalData."""
        item = valid_adyen_notification_item.copy()
        item["additionalData"] = None

        unified_event, result = transformer.transform(item)

        assert result.is_valid is True
        # card_brand falls back to payment method (visa -> visa brand map)
        assert unified_event.card_brand == "visa"
        # card_last_four requires additionalData.cardSummary
        assert unified_event.card_last_four is None

    def test_transform_status_mapping(self, transformer, valid_adyen_notification_item):
        """Test status mapping for different event codes."""
        status_tests = [
            ("AUTHORISATION", True, "authorized"),
            ("CAPTURE", True, "captured"),
            ("CANCELLATION", True, "canceled"),
            ("REFUND", True, "refunded"),
            ("CHARGEBACK", True, "disputed"),
            ("PENDING", True, "pending"),
            ("AUTHORISATION", False, "failed"),  # Failed auth
        ]

        for event_code, success, expected_status in status_tests:
            item = valid_adyen_notification_item.copy()
            item["eventCode"] = event_code
            item["success"] = success

            unified_event, result = transformer.transform(item)

            assert result.is_valid is True, f"Validation failed for {event_code}"
            assert unified_event.status == expected_status, (
                f"Expected status {expected_status} for {event_code} "
                f"(success={success}), got {unified_event.status}"
            )

    def test_transform_failure_code_extraction(self, transformer, valid_adyen_notification_item):
        """Test failure code extraction from reason."""
        failure_tests = [
            ("Card Expired", "expired_card"),
            ("Insufficient Funds", "insufficient_funds"),
            ("Transaction Declined", "declined"),
            ("Suspected Fraud", "fraud"),
            ("Invalid Card Number", "invalid_card"),
            ("Card Blocked", "blocked"),
            ("Unknown Error", "unknown"),
        ]

        for reason, expected_code in failure_tests:
            item = valid_adyen_notification_item.copy()
            item["success"] = False
            item["reason"] = reason

            unified_event, result = transformer.transform(item)

            assert result.is_valid is True
            assert unified_event.failure_code == expected_code, (
                f"Expected failure code {expected_code} for reason '{reason}'"
            )

    def test_transform_parses_timestamp(self, transformer, valid_adyen_notification_item):
        """Test that timestamps are parsed correctly."""
        unified_event, result = transformer.transform(valid_adyen_notification_item)

        assert result.is_valid is True
        assert unified_event.provider_created_at.year == 2024
        assert unified_event.provider_created_at.month == 1
        assert unified_event.provider_created_at.day == 15
        assert unified_event.provider_created_at.hour == 12

    def test_transform_handles_invalid_timestamp(self, transformer, valid_adyen_notification_item):
        """Test handling of invalid timestamps."""
        item = valid_adyen_notification_item.copy()
        item["eventDate"] = "not-a-valid-date"

        unified_event, result = transformer.transform(item)

        # Should still succeed, falling back to current time
        assert result.is_valid is True
        assert unified_event.provider_created_at is not None
