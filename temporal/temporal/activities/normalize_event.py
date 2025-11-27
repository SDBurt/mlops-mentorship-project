# temporal/activities/normalize_event.py
"""
Event normalization activity.

Transforms and cleans payment event data to a consistent internal format.
Handles provider-specific quirks and ensures data consistency.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

from temporalio import activity


@dataclass
class NormalizedFailedPayment:
    """
    Normalized failed payment event for recovery workflow.

    This is the internal representation after validation and normalization,
    ready for ML enrichment and retry strategy prediction.
    """
    # Provider identification
    provider: str
    provider_payment_id: str

    # Transaction details
    amount_cents: int
    currency: str  # Uppercase ISO 4217

    # Customer information
    customer_id: str
    customer_email: str
    customer_name: str

    # Card details
    card_brand: str  # Lowercase normalized
    card_last4: str
    card_exp_month: int
    card_exp_year: int
    card_funding: str  # "credit", "debit", "prepaid", "unknown"

    # Merchant information
    merchant_name: str
    merchant_category: str
    merchant_mcc: str

    # Billing address (normalized)
    billing_country: str  # Uppercase ISO 3166-1 alpha-2
    billing_postal_code: str
    billing_state: str
    billing_city: str

    # Failure details
    failure_code: str
    failure_message: str
    failure_timestamp: str  # ISO 8601
    original_charge_id: str

    # Retry tracking
    retry_count: int

    # Metadata
    created_at: str  # ISO 8601
    normalized_at: str  # ISO 8601

    # Original data reference (ID only, not full data)
    raw_event_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for workflow."""
        return asdict(self)


def _normalize_string(value: Any, default: str = "") -> str:
    """Normalize string values - trim whitespace, handle None."""
    if value is None:
        return default
    return str(value).strip()


def _normalize_currency(value: Any) -> str:
    """Normalize currency code to uppercase."""
    if not value:
        return "USD"
    return str(value).strip().upper()


def _normalize_card_brand(value: Any) -> str:
    """Normalize card brand to lowercase."""
    if not value:
        return "unknown"

    brand = str(value).strip().lower()

    # Handle various representations
    brand_mapping = {
        "american express": "amex",
        "american_express": "amex",
        "master card": "mastercard",
        "master_card": "mastercard",
    }

    return brand_mapping.get(brand, brand)


def _normalize_country(value: Any) -> str:
    """Normalize country code to uppercase ISO 3166-1 alpha-2."""
    if not value:
        return ""

    country = str(value).strip().upper()

    # Handle some common variations
    country_mapping = {
        "USA": "US",
        "UNITED STATES": "US",
        "UNITED STATES OF AMERICA": "US",
        "CANADA": "CA",
        "GREAT BRITAIN": "GB",
        "UNITED KINGDOM": "GB",
        "UK": "GB",
    }

    return country_mapping.get(country, country)


def _normalize_amount(value: Any) -> int:
    """
    Normalize amount to integer cents.

    Handles:
    - String amounts ("1000")
    - Float amounts (10.00 interpreted as dollars -> 1000 cents)
    - Integer amounts (assumed cents)
    """
    if value is None:
        return 0

    if isinstance(value, str):
        try:
            # Try to parse as integer first
            return int(value)
        except ValueError:
            try:
                # Try as float (might be dollars with decimals)
                float_val = float(value)
                # If it has decimals, assume it's dollars
                if float_val != int(float_val):
                    return int(float_val * 100)
                return int(float_val)
            except ValueError:
                return 0

    if isinstance(value, float):
        # Float amounts might be dollars - check if reasonable as cents
        if value < 100:  # Likely dollars
            return int(value * 100)
        return int(value)

    if isinstance(value, int):
        return value

    return 0


def _normalize_card_funding(value: Any) -> str:
    """Normalize card funding type."""
    if not value:
        return "unknown"

    funding = str(value).strip().lower()

    if funding in ("credit", "debit", "prepaid"):
        return funding

    # Handle Square's format
    if funding == "credit_card":
        return "credit"
    if funding == "debit_card":
        return "debit"

    return "unknown"


def _normalize_timestamp(value: Any) -> str:
    """Normalize timestamp to ISO 8601 format."""
    if not value:
        return datetime.utcnow().isoformat() + "Z"

    if isinstance(value, datetime):
        return value.isoformat() + "Z"

    # Already a string - try to parse and reformat
    timestamp_str = str(value).strip()

    # Already ISO format
    if "T" in timestamp_str:
        # Ensure Z suffix
        if not timestamp_str.endswith("Z") and "+" not in timestamp_str:
            timestamp_str += "Z"
        return timestamp_str

    # Try common formats
    common_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
    ]

    for fmt in common_formats:
        try:
            dt = datetime.strptime(timestamp_str, fmt)
            return dt.isoformat() + "Z"
        except ValueError:
            continue

    # Return as-is if we can't parse
    return timestamp_str


def _compute_event_hash(event_data: dict) -> str:
    """Compute a hash for the original event (for traceability)."""
    import hashlib
    import json

    # Use provider + payment ID as a stable identifier
    key = f"{event_data.get('provider', '')}:{event_data.get('provider_payment_id', '')}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


@activity.defn
async def normalize_event(event_data: dict) -> NormalizedFailedPayment:
    """
    Normalize a validated payment event to internal format.

    This activity transforms provider-specific data formats to a consistent
    internal representation, handling various quirks and edge cases.

    Args:
        event_data: Validated failed payment event data

    Returns:
        NormalizedFailedPayment ready for enrichment
    """
    activity.logger.info("Normalizing payment event")

    # Get the payment data (may be nested or flat)
    payment = event_data.get("payment", event_data)
    billing = payment.get("billing_address", {})

    if not isinstance(billing, dict):
        billing = {}

    normalized = NormalizedFailedPayment(
        # Provider identification
        provider=_normalize_string(payment.get("provider")),
        provider_payment_id=_normalize_string(payment.get("provider_payment_id")),

        # Transaction details
        amount_cents=_normalize_amount(
            payment.get("amount_cents", payment.get("amount"))
        ),
        currency=_normalize_currency(payment.get("currency")),

        # Customer information
        customer_id=_normalize_string(payment.get("customer_id")),
        customer_email=_normalize_string(payment.get("customer_email")),
        customer_name=_normalize_string(payment.get("customer_name")),

        # Card details
        card_brand=_normalize_card_brand(payment.get("card_brand")),
        card_last4=_normalize_string(payment.get("card_last4")),
        card_exp_month=int(payment.get("card_exp_month", 0) or 0),
        card_exp_year=int(payment.get("card_exp_year", 0) or 0),
        card_funding=_normalize_card_funding(payment.get("card_funding")),

        # Merchant information
        merchant_name=_normalize_string(payment.get("merchant_name")),
        merchant_category=_normalize_string(payment.get("merchant_category")),
        merchant_mcc=_normalize_string(payment.get("merchant_mcc")),

        # Billing address (normalized)
        billing_country=_normalize_country(billing.get("country")),
        billing_postal_code=_normalize_string(billing.get("postal_code")),
        billing_state=_normalize_string(billing.get("state")),
        billing_city=_normalize_string(billing.get("city")),

        # Failure details
        failure_code=_normalize_string(event_data.get("failure_code")),
        failure_message=_normalize_string(event_data.get("failure_message")),
        failure_timestamp=_normalize_timestamp(event_data.get("failure_timestamp")),
        original_charge_id=_normalize_string(event_data.get("original_charge_id")),

        # Retry tracking
        retry_count=int(event_data.get("retry_count", 0) or 0),

        # Metadata
        created_at=_normalize_timestamp(payment.get("created_at")),
        normalized_at=datetime.utcnow().isoformat() + "Z",

        # Traceability
        raw_event_hash=_compute_event_hash(event_data),
    )

    activity.logger.info(
        f"Normalized event: provider={normalized.provider}, "
        f"payment_id={normalized.provider_payment_id}, "
        f"failure={normalized.failure_code}"
    )

    return normalized
