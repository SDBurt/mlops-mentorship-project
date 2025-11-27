# temporal/activities/validate_event.py
"""
Event validation activity.

Comprehensive validation of incoming payment events with focus on data quality.
This addresses the key concern from Butter's job posting:
"Is it null, NULL, or 'null'? Is 342 a valid country abbreviation code?"

Invalid events are quarantined for manual review rather than processed.
"""
import re
from dataclasses import dataclass, field
from typing import Any

from temporalio import activity


# Null variants to detect across different data sources
NULL_VARIANTS = {
    None,
    "null", "NULL", "Null",
    "none", "NONE", "None",
    "", " ", "  ",
    "undefined", "UNDEFINED", "Undefined",
    "nil", "NIL", "Nil",
    "n/a", "N/A", "NA", "na",
    "\\N",  # Common in database exports
}

# ISO 3166-1 alpha-2 country codes (common subset)
VALID_COUNTRY_CODES = {
    "US", "CA", "GB", "DE", "FR", "AU", "JP", "MX", "BR", "IN",
    "IT", "ES", "NL", "SE", "NO", "DK", "FI", "CH", "AT", "BE",
    "IE", "NZ", "SG", "HK", "KR", "CN", "TW", "PL", "PT", "CZ",
    "RU", "ZA", "AE", "IL", "AR", "CL", "CO", "PE", "PH", "MY",
    "TH", "ID", "VN", "EG", "NG", "KE", "GH", "MA", "TR", "SA",
}

# ISO 4217 currency codes (common subset)
VALID_CURRENCY_CODES = {
    "USD", "CAD", "GBP", "EUR", "AUD", "JPY", "MXN", "BRL", "INR",
    "CNY", "CHF", "SEK", "NOK", "DKK", "NZD", "SGD", "HKD", "KRW",
    "TWD", "PLN", "CZK", "RUB", "ZAR", "AED", "ILS", "TRY", "SAR",
    "THB", "MYR", "IDR", "PHP", "VND", "EGP", "NGN", "KES", "GHS",
}

# Valid card brands (normalized lowercase)
VALID_CARD_BRANDS = {
    "visa", "mastercard", "amex", "discover", "diners", "jcb", "unionpay",
}

# Email validation regex (basic)
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# Amount limits (in cents)
MIN_AMOUNT_CENTS = 1  # Minimum $0.01
MAX_AMOUNT_CENTS = 10_000_000  # Maximum $100,000


@dataclass
class ValidationError:
    """A single validation error."""
    field: str
    value: Any
    error_type: str  # "null_value", "invalid_type", "invalid_code", "out_of_range", "missing_required", "invalid_format"
    message: str


@dataclass
class ValidationResult:
    """Result of event validation."""
    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    quarantine_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for workflow."""
        return {
            "is_valid": self.is_valid,
            "errors": [
                {
                    "field": e.field,
                    "value": str(e.value)[:100],  # Truncate long values
                    "error_type": e.error_type,
                    "message": e.message,
                }
                for e in self.errors
            ],
            "warnings": self.warnings,
            "quarantine_reason": self.quarantine_reason,
        }


def _is_null_variant(value: Any) -> bool:
    """Check if value is a null variant."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() in NULL_VARIANTS
    return False


def _validate_required_field(
    data: dict,
    field_name: str,
    errors: list[ValidationError],
) -> Any:
    """Validate that a required field exists and is not null."""
    value = data.get(field_name)

    if field_name not in data:
        errors.append(ValidationError(
            field=field_name,
            value=None,
            error_type="missing_required",
            message=f"Required field '{field_name}' is missing",
        ))
        return None

    if _is_null_variant(value):
        errors.append(ValidationError(
            field=field_name,
            value=value,
            error_type="null_value",
            message=f"Field '{field_name}' contains null variant: {repr(value)}",
        ))
        return None

    return value


def _validate_type(
    value: Any,
    field_name: str,
    expected_type: type | tuple[type, ...],
    errors: list[ValidationError],
) -> bool:
    """Validate that a value is of the expected type."""
    if value is None:
        return False

    if not isinstance(value, expected_type):
        errors.append(ValidationError(
            field=field_name,
            value=value,
            error_type="invalid_type",
            message=f"Field '{field_name}' expected {expected_type.__name__ if isinstance(expected_type, type) else 'one of ' + str(expected_type)}, got {type(value).__name__}",
        ))
        return False

    return True


def _validate_country_code(
    value: str,
    field_name: str,
    errors: list[ValidationError],
) -> bool:
    """Validate ISO 3166-1 alpha-2 country code."""
    if not value:
        return False

    # Normalize to uppercase
    normalized = value.strip().upper()

    if normalized not in VALID_COUNTRY_CODES:
        errors.append(ValidationError(
            field=field_name,
            value=value,
            error_type="invalid_code",
            message=f"Invalid country code '{value}'. Expected ISO 3166-1 alpha-2 code.",
        ))
        return False

    return True


def _validate_currency_code(
    value: str,
    field_name: str,
    errors: list[ValidationError],
) -> bool:
    """Validate ISO 4217 currency code."""
    if not value:
        return False

    normalized = value.strip().upper()

    if normalized not in VALID_CURRENCY_CODES:
        errors.append(ValidationError(
            field=field_name,
            value=value,
            error_type="invalid_code",
            message=f"Invalid currency code '{value}'. Expected ISO 4217 code.",
        ))
        return False

    return True


def _validate_card_brand(
    value: str,
    field_name: str,
    errors: list[ValidationError],
) -> bool:
    """Validate card brand."""
    if not value:
        return False

    normalized = value.strip().lower()

    if normalized not in VALID_CARD_BRANDS:
        errors.append(ValidationError(
            field=field_name,
            value=value,
            error_type="invalid_code",
            message=f"Unknown card brand '{value}'.",
        ))
        return False

    return True


def _validate_amount(
    value: Any,
    field_name: str,
    errors: list[ValidationError],
) -> bool:
    """Validate payment amount in cents."""
    if value is None:
        return False

    # Handle string amounts (common from some providers)
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            errors.append(ValidationError(
                field=field_name,
                value=value,
                error_type="invalid_type",
                message=f"Amount '{value}' cannot be converted to integer.",
            ))
            return False

    if not isinstance(value, (int, float)):
        errors.append(ValidationError(
            field=field_name,
            value=value,
            error_type="invalid_type",
            message=f"Amount must be numeric, got {type(value).__name__}.",
        ))
        return False

    if value < MIN_AMOUNT_CENTS:
        errors.append(ValidationError(
            field=field_name,
            value=value,
            error_type="out_of_range",
            message=f"Amount {value} is below minimum ({MIN_AMOUNT_CENTS} cents).",
        ))
        return False

    if value > MAX_AMOUNT_CENTS:
        errors.append(ValidationError(
            field=field_name,
            value=value,
            error_type="out_of_range",
            message=f"Amount {value} exceeds maximum ({MAX_AMOUNT_CENTS} cents = ${MAX_AMOUNT_CENTS/100:,.2f}).",
        ))
        return False

    return True


def _validate_email(
    value: str,
    field_name: str,
    errors: list[ValidationError],
    warnings: list[str],
) -> bool:
    """Validate email format."""
    if not value:
        return False

    if _is_null_variant(value):
        errors.append(ValidationError(
            field=field_name,
            value=value,
            error_type="null_value",
            message=f"Email contains null variant: {repr(value)}",
        ))
        return False

    if not EMAIL_REGEX.match(value):
        # Email format issues are warnings, not hard errors
        warnings.append(f"Email '{value}' has unusual format")

    return True


def _validate_card_expiry(
    month: Any,
    year: Any,
    errors: list[ValidationError],
    warnings: list[str],
) -> bool:
    """Validate card expiration date."""
    from datetime import datetime

    try:
        month_int = int(month) if month else 0
        year_int = int(year) if year else 0
    except (ValueError, TypeError):
        errors.append(ValidationError(
            field="card_exp_month/year",
            value=f"{month}/{year}",
            error_type="invalid_type",
            message=f"Card expiry must be numeric: month={month}, year={year}",
        ))
        return False

    if month_int < 1 or month_int > 12:
        errors.append(ValidationError(
            field="card_exp_month",
            value=month_int,
            error_type="out_of_range",
            message=f"Card expiry month {month_int} is invalid (must be 1-12).",
        ))
        return False

    # Check if card is expired (warning only - might still want to retry)
    now = datetime.utcnow()
    if year_int < now.year or (year_int == now.year and month_int < now.month):
        warnings.append(f"Card appears to be expired: {month_int:02d}/{year_int}")

    # Check if expiry is too far in future (suspicious)
    if year_int > now.year + 20:
        errors.append(ValidationError(
            field="card_exp_year",
            value=year_int,
            error_type="out_of_range",
            message=f"Card expiry year {year_int} is too far in future.",
        ))
        return False

    return True


@activity.defn
async def validate_event(event_data: dict) -> ValidationResult:
    """
    Validate a failed payment event for data quality.

    This activity implements comprehensive validation as emphasized in Butter's
    job posting, handling various null representations, ISO code validation,
    and data type checks.

    Args:
        event_data: The failed payment event data (FailedPaymentEvent.to_dict())

    Returns:
        ValidationResult indicating if event is valid or should be quarantined
    """
    errors: list[ValidationError] = []
    warnings: list[str] = []

    activity.logger.info("Validating payment event")

    # Get the payment data (may be nested or flat)
    payment = event_data.get("payment", event_data)

    # === Required Fields ===
    _validate_required_field(payment, "provider", errors)
    _validate_required_field(payment, "provider_payment_id", errors)
    _validate_required_field(payment, "customer_id", errors)

    # === Amount Validation ===
    amount = payment.get("amount_cents", payment.get("amount"))
    if amount is not None:
        _validate_amount(amount, "amount_cents", errors)
    else:
        errors.append(ValidationError(
            field="amount_cents",
            value=None,
            error_type="missing_required",
            message="Amount is required",
        ))

    # === Currency Validation ===
    currency = _validate_required_field(payment, "currency", errors)
    if currency and _validate_type(currency, "currency", str, errors):
        _validate_currency_code(currency, "currency", errors)

    # === Card Brand Validation ===
    card_brand = payment.get("card_brand")
    if card_brand and not _is_null_variant(card_brand):
        _validate_card_brand(card_brand, "card_brand", errors)

    # === Card Expiry Validation ===
    exp_month = payment.get("card_exp_month")
    exp_year = payment.get("card_exp_year")
    if exp_month is not None and exp_year is not None:
        _validate_card_expiry(exp_month, exp_year, errors, warnings)

    # === Email Validation ===
    email = payment.get("customer_email")
    if email and not _is_null_variant(email):
        _validate_email(email, "customer_email", errors, warnings)

    # === Billing Address Country Validation ===
    billing = payment.get("billing_address", {})
    if isinstance(billing, dict):
        country = billing.get("country")
        if country and not _is_null_variant(country):
            _validate_country_code(country, "billing_address.country", errors)

    # === Failure Event Fields ===
    failure_code = event_data.get("failure_code")
    if not failure_code or _is_null_variant(failure_code):
        errors.append(ValidationError(
            field="failure_code",
            value=failure_code,
            error_type="missing_required",
            message="Failure code is required for failed payment events",
        ))

    # Determine if valid
    is_valid = len(errors) == 0
    quarantine_reason = None

    if not is_valid:
        # Determine primary quarantine reason
        error_types = {e.error_type for e in errors}
        if "missing_required" in error_types:
            quarantine_reason = "missing_required_fields"
        elif "null_value" in error_types:
            quarantine_reason = "null_values_detected"
        elif "invalid_code" in error_types:
            quarantine_reason = "invalid_codes"
        elif "out_of_range" in error_types:
            quarantine_reason = "values_out_of_range"
        else:
            quarantine_reason = "validation_failed"

    result = ValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        quarantine_reason=quarantine_reason,
    )

    activity.logger.info(
        f"Validation complete: valid={is_valid}, "
        f"errors={len(errors)}, warnings={len(warnings)}"
    )

    return result
