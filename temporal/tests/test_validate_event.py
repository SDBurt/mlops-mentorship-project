# tests/test_validate_event.py
"""
Unit tests for the validate_event activity.

Tests comprehensive validation including null variants, ISO code validation,
and quarantine logic.
"""
import pytest

from temporal.activities.validate_event import (
    validate_event,
    ValidationResult,
    ValidationError,
    _is_null_variant,
    VALID_COUNTRY_CODES,
    VALID_CURRENCY_CODES,
)


# Use the mock_activity_logger fixture from conftest for all tests in this module
pytestmark = pytest.mark.usefixtures("mock_activity_logger")


@pytest.fixture
def valid_failed_payment_event() -> dict:
    """A valid failed payment event for testing."""
    return {
        "payment": {
            "provider": "stripe",
            "provider_payment_id": "pi_test123",
            "amount_cents": 5000,
            "currency": "USD",
            "customer_id": "cus_456",
            "customer_email": "test@example.com",
            "customer_name": "Test User",
            "card_brand": "visa",
            "card_last4": "4242",
            "card_exp_month": 12,
            "card_exp_year": 2026,
            "card_funding": "credit",
            "billing_address": {
                "country": "US",
                "postal_code": "94105",
                "state": "CA",
                "city": "San Francisco",
            },
        },
        "failure_code": "card_declined",
        "failure_message": "Your card was declined.",
        "failure_timestamp": "2024-01-01T00:00:00Z",
        "original_charge_id": "ch_test123",
        "retry_count": 0,
    }


class TestNullVariantDetection:
    """Tests for null variant detection."""

    @pytest.mark.parametrize("value", [
        None,
        "null", "NULL", "Null",
        "none", "NONE", "None",
        "", " ", "  ",
        "undefined", "UNDEFINED",
        "nil", "NIL",
        "n/a", "N/A", "NA",
    ])
    def test_detects_null_variants(self, value):
        """Should detect various null representations."""
        assert _is_null_variant(value) is True

    @pytest.mark.parametrize("value", [
        "valid_string",
        "0",
        "false",
        "hello",
        123,
        0,
        False,
    ])
    def test_does_not_flag_valid_values(self, value):
        """Should not flag valid non-null values."""
        assert _is_null_variant(value) is False


class TestValidateEvent:
    """Tests for the validate_event activity."""

    @pytest.mark.asyncio
    async def test_valid_event_passes(self, valid_failed_payment_event):
        """Valid event should pass validation."""
        result = await validate_event(valid_failed_payment_event)

        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.quarantine_reason is None

    @pytest.mark.asyncio
    async def test_missing_provider_fails(self, valid_failed_payment_event):
        """Missing provider should fail validation."""
        del valid_failed_payment_event["payment"]["provider"]

        result = await validate_event(valid_failed_payment_event)

        assert result.is_valid is False
        error_fields = [e.field for e in result.errors]
        assert "provider" in error_fields

    @pytest.mark.asyncio
    async def test_null_provider_fails(self, valid_failed_payment_event):
        """Null provider should fail validation."""
        valid_failed_payment_event["payment"]["provider"] = "null"

        result = await validate_event(valid_failed_payment_event)

        assert result.is_valid is False
        error_types = [e.error_type for e in result.errors]
        assert "null_value" in error_types

    @pytest.mark.asyncio
    async def test_missing_payment_id_fails(self, valid_failed_payment_event):
        """Missing payment ID should fail validation."""
        del valid_failed_payment_event["payment"]["provider_payment_id"]

        result = await validate_event(valid_failed_payment_event)

        assert result.is_valid is False
        error_fields = [e.field for e in result.errors]
        assert "provider_payment_id" in error_fields

    @pytest.mark.asyncio
    async def test_missing_customer_id_fails(self, valid_failed_payment_event):
        """Missing customer ID should fail validation."""
        del valid_failed_payment_event["payment"]["customer_id"]

        result = await validate_event(valid_failed_payment_event)

        assert result.is_valid is False
        error_fields = [e.field for e in result.errors]
        assert "customer_id" in error_fields


class TestCurrencyValidation:
    """Tests for ISO 4217 currency code validation."""

    @pytest.mark.asyncio
    async def test_valid_currency_passes(self, valid_failed_payment_event):
        """Valid currency code should pass."""
        valid_failed_payment_event["payment"]["currency"] = "EUR"

        result = await validate_event(valid_failed_payment_event)

        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_invalid_currency_fails(self, valid_failed_payment_event):
        """Invalid currency code should fail."""
        valid_failed_payment_event["payment"]["currency"] = "XXX"

        result = await validate_event(valid_failed_payment_event)

        assert result.is_valid is False
        errors = [e for e in result.errors if e.field == "currency"]
        assert len(errors) == 1
        assert errors[0].error_type == "invalid_code"

    @pytest.mark.asyncio
    async def test_lowercase_currency_passes(self, valid_failed_payment_event):
        """Lowercase currency code should pass (normalized)."""
        valid_failed_payment_event["payment"]["currency"] = "usd"

        result = await validate_event(valid_failed_payment_event)

        # Currency validation normalizes to uppercase
        assert result.is_valid is True


class TestCountryCodeValidation:
    """Tests for ISO 3166-1 alpha-2 country code validation."""

    @pytest.mark.asyncio
    async def test_valid_country_passes(self, valid_failed_payment_event):
        """Valid country code should pass."""
        valid_failed_payment_event["payment"]["billing_address"]["country"] = "CA"

        result = await validate_event(valid_failed_payment_event)

        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_invalid_country_code_fails(self, valid_failed_payment_event):
        """Invalid country code should fail."""
        valid_failed_payment_event["payment"]["billing_address"]["country"] = "342"

        result = await validate_event(valid_failed_payment_event)

        assert result.is_valid is False
        errors = [e for e in result.errors if "country" in e.field]
        assert len(errors) == 1
        assert errors[0].error_type == "invalid_code"


class TestAmountValidation:
    """Tests for amount validation."""

    @pytest.mark.asyncio
    async def test_valid_amount_passes(self, valid_failed_payment_event):
        """Valid amount should pass."""
        valid_failed_payment_event["payment"]["amount_cents"] = 10000

        result = await validate_event(valid_failed_payment_event)

        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_negative_amount_fails(self, valid_failed_payment_event):
        """Negative amount should fail."""
        valid_failed_payment_event["payment"]["amount_cents"] = -100

        result = await validate_event(valid_failed_payment_event)

        assert result.is_valid is False
        errors = [e for e in result.errors if e.field == "amount_cents"]
        assert len(errors) == 1
        assert errors[0].error_type == "out_of_range"

    @pytest.mark.asyncio
    async def test_zero_amount_fails(self, valid_failed_payment_event):
        """Zero amount should fail (below minimum)."""
        valid_failed_payment_event["payment"]["amount_cents"] = 0

        result = await validate_event(valid_failed_payment_event)

        assert result.is_valid is False
        errors = [e for e in result.errors if e.field == "amount_cents"]
        assert len(errors) == 1

    @pytest.mark.asyncio
    async def test_very_large_amount_fails(self, valid_failed_payment_event):
        """Very large amount should fail."""
        valid_failed_payment_event["payment"]["amount_cents"] = 100_000_000  # $1M

        result = await validate_event(valid_failed_payment_event)

        assert result.is_valid is False
        errors = [e for e in result.errors if e.field == "amount_cents"]
        assert len(errors) == 1
        assert errors[0].error_type == "out_of_range"


class TestFailureCodeValidation:
    """Tests for failure code validation."""

    @pytest.mark.asyncio
    async def test_missing_failure_code_fails(self, valid_failed_payment_event):
        """Missing failure code should fail."""
        del valid_failed_payment_event["failure_code"]

        result = await validate_event(valid_failed_payment_event)

        assert result.is_valid is False
        error_fields = [e.field for e in result.errors]
        assert "failure_code" in error_fields

    @pytest.mark.asyncio
    async def test_null_failure_code_fails(self, valid_failed_payment_event):
        """Null failure code should fail."""
        valid_failed_payment_event["failure_code"] = None

        result = await validate_event(valid_failed_payment_event)

        assert result.is_valid is False


class TestQuarantineReasons:
    """Tests for quarantine reason assignment."""

    @pytest.mark.asyncio
    async def test_missing_required_quarantine_reason(self, valid_failed_payment_event):
        """Missing required fields should set correct quarantine reason."""
        del valid_failed_payment_event["payment"]["provider"]

        result = await validate_event(valid_failed_payment_event)

        assert result.quarantine_reason == "missing_required_fields"

    @pytest.mark.asyncio
    async def test_null_value_quarantine_reason(self, valid_failed_payment_event):
        """Null values should set correct quarantine reason."""
        valid_failed_payment_event["payment"]["provider"] = "NULL"

        result = await validate_event(valid_failed_payment_event)

        assert result.quarantine_reason == "null_values_detected"

    @pytest.mark.asyncio
    async def test_invalid_code_quarantine_reason(self, valid_failed_payment_event):
        """Invalid codes should set correct quarantine reason."""
        valid_failed_payment_event["payment"]["currency"] = "INVALID"

        result = await validate_event(valid_failed_payment_event)

        assert result.quarantine_reason == "invalid_codes"


class TestValidationResultSerialization:
    """Tests for ValidationResult serialization."""

    @pytest.mark.asyncio
    async def test_to_dict_works(self, valid_failed_payment_event):
        """ValidationResult.to_dict should serialize correctly."""
        valid_failed_payment_event["payment"]["currency"] = "INVALID"

        result = await validate_event(valid_failed_payment_event)
        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert "is_valid" in result_dict
        assert "errors" in result_dict
        assert "warnings" in result_dict
        assert "quarantine_reason" in result_dict
        assert isinstance(result_dict["errors"], list)


class TestFlatPaymentFormat:
    """Tests for handling flat (non-nested) payment format."""

    @pytest.mark.asyncio
    async def test_handles_flat_format(self):
        """Should handle flat payment format (no nested 'payment' key)."""
        flat_event = {
            "provider": "stripe",
            "provider_payment_id": "pi_test123",
            "amount_cents": 5000,
            "currency": "USD",
            "customer_id": "cus_456",
            "failure_code": "card_declined",
        }

        result = await validate_event(flat_event)

        assert result.is_valid is True
