"""Unit tests for Braintree event transformer."""

import pytest

from normalizer.transformers.braintree import BraintreeTransformer


class TestBraintreeTransformer:
    """Tests for BraintreeTransformer class."""

    @pytest.fixture
    def transformer(self):
        """Create a BraintreeTransformer instance."""
        return BraintreeTransformer()

    def test_transform_valid_transaction_settled(self, transformer, valid_braintree_transaction_settled):
        """Test transforming a valid transaction_settled notification."""
        unified_event, result = transformer.transform(valid_braintree_transaction_settled)

        assert result.is_valid is True
        assert unified_event is not None
        assert unified_event.event_id == "braintree:transaction_settled_txn_1234567890"
        assert unified_event.provider == "braintree"
        assert unified_event.provider_event_id == "txn_1234567890"
        assert unified_event.event_type == "payment.settled"
        assert unified_event.amount_cents == 2000
        assert unified_event.currency == "USD"
        assert unified_event.status == "settled"
        assert unified_event.customer_id == "customer_123"
        assert unified_event.merchant_id == "merchant_account_123"
        assert unified_event.card_brand == "visa"
        assert unified_event.card_last_four == "1111"
        assert unified_event.payment_method_type == "card"

    def test_transform_valid_subscription_charged(self, transformer, valid_braintree_subscription_charged):
        """Test transforming a valid subscription_charged_successfully notification."""
        unified_event, result = transformer.transform(valid_braintree_subscription_charged)

        assert result.is_valid is True
        assert unified_event is not None
        assert unified_event.event_type == "subscription.charged"
        assert unified_event.amount_cents == 999
        assert unified_event.status == "succeeded"
        assert unified_event.metadata.get("subscription") is not None

    def test_transform_valid_dispute_opened(self, transformer, valid_braintree_dispute_opened):
        """Test transforming a valid dispute_opened notification."""
        unified_event, result = transformer.transform(valid_braintree_dispute_opened)

        assert result.is_valid is True
        assert unified_event is not None
        assert unified_event.event_type == "dispute.created"
        assert unified_event.status == "disputed"
        assert unified_event.metadata.get("dispute") is not None

    def test_transform_missing_kind(self, transformer, valid_braintree_transaction_settled):
        """Test that missing kind causes validation failure."""
        event = valid_braintree_transaction_settled.copy()
        del event["kind"]

        unified_event, result = transformer.transform(event)

        assert result.is_valid is False
        assert "MISSING_KIND" in result.error_codes
        assert unified_event is None

    def test_transform_transaction_missing_id(self, transformer, valid_braintree_transaction_settled):
        """Test that transaction notification without transaction ID fails."""
        event = valid_braintree_transaction_settled.copy()
        event["transaction"] = {}

        unified_event, result = transformer.transform(event)

        assert result.is_valid is False
        assert "MISSING_TRANSACTION_ID" in result.error_codes

    def test_transform_invalid_currency(self, transformer, valid_braintree_transaction_settled):
        """Test that invalid currency causes validation failure."""
        event = valid_braintree_transaction_settled.copy()
        event["transaction"]["currency_iso_code"] = "XYZ"

        unified_event, result = transformer.transform(event)

        assert result.is_valid is False
        assert "INVALID_CURRENCY" in result.error_codes
        assert unified_event is None

    def test_transform_invalid_amount(self, transformer, valid_braintree_transaction_settled):
        """Test that invalid amount format causes validation failure."""
        event = valid_braintree_transaction_settled.copy()
        event["transaction"]["amount"] = "not_a_number"

        unified_event, result = transformer.transform(event)

        assert result.is_valid is False
        assert any("INVALID_AMOUNT" in code for code in result.error_codes)

    def test_transform_normalizes_payment_method(self, transformer, valid_braintree_transaction_settled):
        """Test that payment methods are normalized correctly."""
        test_cases = [
            ("credit_card", "card"),
            ("paypal_account", "paypal"),
            ("venmo_account", "venmo"),
            ("apple_pay_card", "wallet"),
            ("google_pay_card", "wallet"),
            ("us_bank_account", "bank_account"),
        ]

        for braintree_method, expected in test_cases:
            event = valid_braintree_transaction_settled.copy()
            event["transaction"] = event["transaction"].copy()
            event["transaction"]["payment_instrument_type"] = braintree_method

            unified_event, result = transformer.transform(event)

            assert result.is_valid is True
            assert unified_event.payment_method_type == expected, (
                f"Expected {expected} for {braintree_method}"
            )

    def test_transform_normalizes_card_brand(self, transformer, valid_braintree_transaction_settled):
        """Test that card brands are normalized correctly."""
        test_cases = [
            ("Visa", "visa"),
            ("MasterCard", "mastercard"),
            ("American Express", "amex"),
            ("Discover", "discover"),
        ]

        for braintree_brand, expected in test_cases:
            event = valid_braintree_transaction_settled.copy()
            event["transaction"] = event["transaction"].copy()
            event["transaction"]["card_details"] = {"card_type": braintree_brand, "last_4": "1234"}

            unified_event, result = transformer.transform(event)

            assert result.is_valid is True
            assert unified_event.card_brand == expected, (
                f"Expected {expected} for {braintree_brand}"
            )

    def test_transform_extracts_metadata(self, transformer, valid_braintree_transaction_settled):
        """Test that metadata is correctly extracted."""
        unified_event, result = transformer.transform(valid_braintree_transaction_settled)

        assert result.is_valid is True
        assert unified_event.metadata.get("kind") == "transaction_settled"
        assert unified_event.metadata.get("transaction_type") == "sale"

    def test_transform_handles_missing_card_details(self, transformer, valid_braintree_transaction_settled):
        """Test handling of notifications without card details."""
        event = valid_braintree_transaction_settled.copy()
        event["transaction"] = event["transaction"].copy()
        del event["transaction"]["card_details"]

        unified_event, result = transformer.transform(event)

        assert result.is_valid is True
        assert unified_event.card_brand is None
        assert unified_event.card_last_four is None

    def test_transform_status_mapping(self, transformer, valid_braintree_transaction_settled):
        """Test status mapping for different notification kinds."""
        status_tests = [
            ("transaction_settled", "settled"),
            ("transaction_settlement_declined", "settlement_declined"),
            ("subscription_charged_successfully", "succeeded"),
            ("subscription_charged_unsuccessfully", "failed"),
            ("subscription_canceled", "canceled"),
            ("dispute_opened", "disputed"),
            ("dispute_won", "dispute_won"),
            ("dispute_lost", "dispute_lost"),
        ]

        for kind, expected_status in status_tests:
            event = valid_braintree_transaction_settled.copy()
            event["kind"] = kind

            unified_event, result = transformer.transform(event)

            assert result.is_valid is True, f"Validation failed for {kind}"
            assert unified_event.status == expected_status, (
                f"Expected status {expected_status} for {kind}, got {unified_event.status}"
            )

    def test_transform_parses_timestamp(self, transformer, valid_braintree_transaction_settled):
        """Test that timestamps are parsed correctly."""
        unified_event, result = transformer.transform(valid_braintree_transaction_settled)

        assert result.is_valid is True
        assert unified_event.provider_created_at.year == 2024
        assert unified_event.provider_created_at.month == 1
        assert unified_event.provider_created_at.day == 15
        assert unified_event.provider_created_at.hour == 12

    def test_transform_handles_invalid_timestamp(self, transformer, valid_braintree_transaction_settled):
        """Test handling of invalid timestamps."""
        event = valid_braintree_transaction_settled.copy()
        event["timestamp"] = "not-a-valid-date"

        unified_event, result = transformer.transform(event)

        # Should still succeed, falling back to current time
        assert result.is_valid is True
        assert unified_event.provider_created_at is not None

    def test_transform_non_transaction_event(self, transformer):
        """Test transforming a non-transaction event (like check)."""
        event = {
            "kind": "check",
            "timestamp": "2024-01-15T12:00:00+00:00",
        }

        unified_event, result = transformer.transform(event)

        # check event doesn't require transaction, so should pass
        assert result.is_valid is True
        assert unified_event.event_type == "check.verified"
        assert unified_event.amount_cents == 0
