"""Unit tests for normalizer validators."""

import pytest

from normalizer.validators import (
    AmountValidator,
    CurrencyValidator,
    ValidationError,
    ValidationResult,
    normalize_null,
    normalize_null_string,
)
from normalizer.validators.amount import MAX_AMOUNT_CENTS, RefundAmountValidator
from normalizer.validators.currency import SUPPORTED_CURRENCIES


class TestNullNormalization:
    """Tests for null normalization utilities."""

    @pytest.mark.parametrize(
        "input_value,expected",
        [
            (None, None),
            ("", None),
            ("null", None),
            ("NULL", None),
            ("Null", None),
            ("none", None),
            ("None", None),
            ("NONE", None),
        ],
    )
    def test_normalize_null_converts_null_representations(self, input_value, expected):
        """Test that various null representations are converted to None."""
        assert normalize_null(input_value) == expected

    @pytest.mark.parametrize(
        "input_value",
        [
            "hello",
            "   ",  # Whitespace is not null
            "0",
            "false",
            "undefined",
            123,
            0,
            False,
            [],
            {},
        ],
    )
    def test_normalize_null_preserves_non_null_values(self, input_value):
        """Test that non-null values are preserved."""
        assert normalize_null(input_value) == input_value

    @pytest.mark.parametrize(
        "input_value,expected",
        [
            (None, None),
            ("", None),
            ("null", None),
            ("valid_string", "valid_string"),
        ],
    )
    def test_normalize_null_string(self, input_value, expected):
        """Test null string normalization."""
        assert normalize_null_string(input_value) == expected


class TestCurrencyValidator:
    """Tests for currency validation."""

    def test_valid_currencies(self):
        """Test that supported currencies are valid."""
        validator = CurrencyValidator()
        for currency in ["USD", "EUR", "GBP", "JPY", "CAD"]:
            is_valid, normalized, error = validator.validate(currency)
            assert is_valid is True
            assert normalized == currency
            assert error is None

    def test_lowercase_currency_normalized_to_uppercase(self):
        """Test that lowercase currencies are normalized to uppercase."""
        validator = CurrencyValidator()
        is_valid, normalized, error = validator.validate("usd")
        assert is_valid is True
        assert normalized == "USD"
        assert error is None

    def test_mixed_case_currency_normalized(self):
        """Test that mixed case currencies are normalized."""
        validator = CurrencyValidator()
        is_valid, normalized, error = validator.validate("Usd")
        assert is_valid is True
        assert normalized == "USD"
        assert error is None

    def test_whitespace_stripped(self):
        """Test that whitespace is stripped from currencies."""
        validator = CurrencyValidator()
        is_valid, normalized, error = validator.validate("  USD  ")
        assert is_valid is True
        assert normalized == "USD"
        assert error is None

    def test_none_currency_invalid(self):
        """Test that None currency is invalid."""
        validator = CurrencyValidator()
        is_valid, normalized, error = validator.validate(None)
        assert is_valid is False
        assert normalized is None
        assert "required" in error.lower()

    def test_empty_currency_invalid(self):
        """Test that empty currency is invalid."""
        validator = CurrencyValidator()
        is_valid, normalized, error = validator.validate("")
        assert is_valid is False
        assert normalized is None
        assert "empty" in error.lower()

    def test_invalid_length_currency(self):
        """Test that currencies with wrong length are invalid."""
        validator = CurrencyValidator()
        for currency in ["US", "USDD", "A", "ABCDE"]:
            is_valid, normalized, error = validator.validate(currency)
            assert is_valid is False
            assert "3 characters" in error

    def test_unsupported_currency(self):
        """Test that unsupported currencies are invalid."""
        validator = CurrencyValidator()
        is_valid, normalized, error = validator.validate("XYZ")
        assert is_valid is False
        assert "Unsupported" in error

    def test_custom_supported_currencies(self):
        """Test custom supported currency set."""
        validator = CurrencyValidator(supported_currencies=frozenset({"BTC", "ETH"}))

        # Custom currencies should be valid
        is_valid, normalized, _ = validator.validate("BTC")
        assert is_valid is True
        assert normalized == "BTC"

        # Standard currencies should be invalid with custom set
        is_valid, _, error = validator.validate("USD")
        assert is_valid is False
        assert "Unsupported" in error

    def test_is_valid_helper(self):
        """Test the is_valid helper method."""
        validator = CurrencyValidator()
        assert validator.is_valid("USD") is True
        assert validator.is_valid("XYZ") is False
        assert validator.is_valid(None) is False

    def test_normalize_helper(self):
        """Test the normalize helper method."""
        validator = CurrencyValidator()
        assert validator.normalize("usd") == "USD"
        assert validator.normalize("  eur  ") == "EUR"


class TestAmountValidator:
    """Tests for amount validation."""

    def test_valid_amounts(self):
        """Test that valid amounts pass validation."""
        validator = AmountValidator()
        for amount in [0, 1, 100, 2000, 100_000_000]:
            is_valid, normalized, error = validator.validate(amount)
            assert is_valid is True
            assert normalized == amount
            assert error is None

    def test_none_amount_invalid(self):
        """Test that None amount is invalid."""
        validator = AmountValidator()
        is_valid, normalized, error = validator.validate(None)
        assert is_valid is False
        assert normalized is None
        assert "required" in error.lower()

    def test_negative_amount_invalid(self):
        """Test that negative amounts are invalid."""
        validator = AmountValidator()
        is_valid, normalized, error = validator.validate(-1)
        assert is_valid is False
        assert ">=" in error

    def test_amount_exceeds_max(self):
        """Test that amounts exceeding max are invalid."""
        validator = AmountValidator()
        is_valid, normalized, error = validator.validate(MAX_AMOUNT_CENTS + 1)
        assert is_valid is False
        assert "<=" in error

    def test_amount_at_max_boundary(self):
        """Test that max amount is valid."""
        validator = AmountValidator()
        is_valid, normalized, error = validator.validate(MAX_AMOUNT_CENTS)
        assert is_valid is True
        assert normalized == MAX_AMOUNT_CENTS

    def test_zero_amount_allowed_by_default(self):
        """Test that zero is allowed by default."""
        validator = AmountValidator()
        is_valid, normalized, error = validator.validate(0)
        assert is_valid is True
        assert normalized == 0

    def test_zero_amount_can_be_disallowed(self):
        """Test that zero can be disallowed."""
        validator = AmountValidator(allow_zero=False)
        is_valid, normalized, error = validator.validate(0)
        assert is_valid is False
        assert "zero" in error.lower()

    def test_custom_min_max(self):
        """Test custom min/max amounts."""
        validator = AmountValidator(min_amount=100, max_amount=1000)

        is_valid, _, _ = validator.validate(500)
        assert is_valid is True

        is_valid, _, _ = validator.validate(50)
        assert is_valid is False

        is_valid, _, _ = validator.validate(1500)
        assert is_valid is False

    def test_string_amount_converted_to_int(self):
        """Test that string amounts are converted to integers."""
        validator = AmountValidator()
        is_valid, normalized, error = validator.validate("1000")
        assert is_valid is True
        assert normalized == 1000

    def test_invalid_string_amount(self):
        """Test that non-numeric strings are invalid."""
        validator = AmountValidator()
        is_valid, normalized, error = validator.validate("abc")
        assert is_valid is False
        assert "integer" in error.lower()

    def test_float_amount_converted(self):
        """Test that float amounts are converted."""
        validator = AmountValidator()
        is_valid, normalized, error = validator.validate(100.0)
        assert is_valid is True
        assert normalized == 100

    def test_is_valid_helper(self):
        """Test the is_valid helper method."""
        validator = AmountValidator()
        assert validator.is_valid(100) is True
        assert validator.is_valid(-1) is False
        assert validator.is_valid(None) is False


class TestRefundAmountValidator:
    """Tests for refund amount validation."""

    def test_zero_refund_allowed(self):
        """Test that zero refunds are allowed."""
        validator = RefundAmountValidator()
        is_valid, normalized, error = validator.validate(0)
        assert is_valid is True
        assert normalized == 0

    def test_positive_refund_valid(self):
        """Test that positive refunds are valid."""
        validator = RefundAmountValidator()
        is_valid, normalized, error = validator.validate(500)
        assert is_valid is True
        assert normalized == 500


class TestValidationResult:
    """Tests for ValidationResult class."""

    def test_initial_valid_state(self):
        """Test that ValidationResult starts valid."""
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.errors == []
        assert result.error_codes == []
        assert result.primary_error_code is None

    def test_add_error_sets_invalid(self):
        """Test that adding an error sets is_valid to False."""
        result = ValidationResult(is_valid=True)
        result.add_error("field", "CODE", "message")
        assert result.is_valid is False
        assert len(result.errors) == 1

    def test_error_codes_property(self):
        """Test the error_codes property."""
        result = ValidationResult(is_valid=True)
        result.add_error("f1", "ERR1", "msg1")
        result.add_error("f2", "ERR2", "msg2")
        assert result.error_codes == ["ERR1", "ERR2"]

    def test_primary_error_code(self):
        """Test the primary_error_code property."""
        result = ValidationResult(is_valid=True)
        result.add_error("f1", "FIRST_ERROR", "msg1")
        result.add_error("f2", "SECOND_ERROR", "msg2")
        assert result.primary_error_code == "FIRST_ERROR"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = ValidationResult(is_valid=True)
        result.add_error("amount", "INVALID_AMOUNT", "Amount is negative")

        d = result.to_dict()
        assert d["is_valid"] is False
        assert len(d["errors"]) == 1
        assert d["errors"][0]["field"] == "amount"
        assert d["errors"][0]["code"] == "INVALID_AMOUNT"


class TestValidationError:
    """Tests for ValidationError class."""

    def test_to_dict(self):
        """Test serialization to dictionary."""
        error = ValidationError(
            field="currency",
            code="INVALID_CURRENCY",
            message="Currency XYZ is not supported",
        )
        d = error.to_dict()
        assert d == {
            "field": "currency",
            "code": "INVALID_CURRENCY",
            "message": "Currency XYZ is not supported",
        }
