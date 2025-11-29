"""Business rules validation activity."""

from typing import Any

from temporalio import activity


# Business rule constants
MAX_AMOUNT_CENTS = 1_000_000_00  # $1,000,000
ALLOWED_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CHF", "CNY", "HKD", "NZD"}

# Mock blocklisted entities (in production, this would come from a database)
BLOCKLISTED_CUSTOMERS = {"cus_blocked_001", "cus_blocked_002", "cus_test_blocked"}
BLOCKLISTED_MERCHANTS = {"merch_blocked_001"}


@activity.defn
async def validate_business_rules(event_data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate payment event against business rules.

    This activity performs final validation that requires business context,
    such as blocklist checks and limit validation.

    Args:
        event_data: Normalized payment event data

    Returns:
        Validation result with is_valid flag and any errors
    """
    activity.logger.info(f"Validating business rules for: {event_data.get('event_id')}")

    errors = []
    warnings = []
    rules_checked = []

    # Rule 1: Amount bounds
    rules_checked.append("amount_bounds")
    amount_cents = event_data.get("amount_cents", 0)
    if amount_cents <= 0:
        errors.append({
            "rule": "amount_bounds",
            "code": "AMOUNT_NOT_POSITIVE",
            "message": "Amount must be greater than zero",
        })
    elif amount_cents > MAX_AMOUNT_CENTS:
        errors.append({
            "rule": "amount_bounds",
            "code": "AMOUNT_EXCEEDS_MAXIMUM",
            "message": f"Amount {amount_cents} exceeds maximum {MAX_AMOUNT_CENTS}",
        })

    # Rule 2: Currency validation
    rules_checked.append("currency_allowed")
    currency = event_data.get("currency", "").upper()
    if currency not in ALLOWED_CURRENCIES:
        errors.append({
            "rule": "currency_allowed",
            "code": "CURRENCY_NOT_ALLOWED",
            "message": f"Currency '{currency}' is not in allowed list",
        })

    # Rule 3: Customer blocklist
    rules_checked.append("customer_blocklist")
    customer_id = event_data.get("customer_id")
    if customer_id and customer_id in BLOCKLISTED_CUSTOMERS:
        errors.append({
            "rule": "customer_blocklist",
            "code": "CUSTOMER_BLOCKLISTED",
            "message": f"Customer '{customer_id}' is blocklisted",
        })

    # Rule 4: Merchant blocklist
    rules_checked.append("merchant_blocklist")
    merchant_id = event_data.get("merchant_id")
    if merchant_id and merchant_id in BLOCKLISTED_MERCHANTS:
        errors.append({
            "rule": "merchant_blocklist",
            "code": "MERCHANT_BLOCKLISTED",
            "message": f"Merchant '{merchant_id}' is blocklisted",
        })

    # Rule 5: Required fields
    rules_checked.append("required_fields")
    required_fields = ["event_id", "provider", "event_type", "status"]
    for field in required_fields:
        if not event_data.get(field):
            errors.append({
                "rule": "required_fields",
                "code": "MISSING_REQUIRED_FIELD",
                "message": f"Required field '{field}' is missing or empty",
            })

    # Warning: High-value transaction
    if amount_cents > 10_000_00:  # > $100
        warnings.append({
            "rule": "high_value_warning",
            "message": f"High-value transaction: {amount_cents} cents",
        })

    is_valid = len(errors) == 0

    activity.logger.info(
        f"Validation complete for {event_data.get('event_id')}: "
        f"valid={is_valid}, errors={len(errors)}, warnings={len(warnings)}"
    )

    return {
        "is_valid": is_valid,
        "errors": errors,
        "warnings": warnings,
        "rules_checked": rules_checked,
    }
