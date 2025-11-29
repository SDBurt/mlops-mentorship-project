"""Stripe event transformer."""

from datetime import datetime, timezone
from typing import Any

from ..validators import ValidationResult, normalize_null_string
from ..validators.amount import AmountValidator
from ..validators.currency import CurrencyValidator
from .base import UnifiedPaymentEvent, normalize_event_type


class StripeTransformer:
    """Transforms Stripe webhook events to unified schema."""

    def __init__(self):
        self.currency_validator = CurrencyValidator()
        self.amount_validator = AmountValidator()

    def transform(self, raw_event: dict[str, Any]) -> tuple[UnifiedPaymentEvent | None, ValidationResult]:
        """
        Transform a raw Stripe event to unified format.

        Args:
            raw_event: Raw Stripe webhook event

        Returns:
            Tuple of (unified_event, validation_result)
            unified_event is None if validation fails
        """
        result = ValidationResult(is_valid=True)

        # Validate required top-level fields
        event_id = raw_event.get("id")
        if not event_id:
            result.add_error("id", "MISSING_EVENT_ID", "Event ID is required")

        event_type = raw_event.get("type")
        if not event_type:
            result.add_error("type", "MISSING_EVENT_TYPE", "Event type is required")

        # Get nested data object
        data = raw_event.get("data", {})
        data_object = data.get("object", {})

        if not data_object:
            result.add_error("data.object", "MISSING_DATA_OBJECT", "Data object is required")
            return None, result

        object_id = data_object.get("id")
        if not object_id:
            result.add_error("data.object.id", "MISSING_OBJECT_ID", "Object ID is required")

        # Validate and normalize amount
        amount = data_object.get("amount")
        amount_valid, normalized_amount, amount_error = self.amount_validator.validate(amount)
        if not amount_valid:
            code = "INVALID_AMOUNT_NEGATIVE" if amount is not None and amount < 0 else "INVALID_AMOUNT"
            if amount is not None and amount > self.amount_validator.max_amount:
                code = "INVALID_AMOUNT_TOO_LARGE"
            result.add_error("data.object.amount", code, amount_error or "Invalid amount")

        # Validate and normalize currency
        currency = data_object.get("currency")
        currency_valid, normalized_currency, currency_error = self.currency_validator.validate(currency)
        if not currency_valid:
            result.add_error("data.object.currency", "INVALID_CURRENCY", currency_error or "Invalid currency")

        # If validation failed, return early
        if not result.is_valid:
            return None, result

        # Extract common fields with null normalization
        customer_id = normalize_null_string(data_object.get("customer"))
        merchant_id = data_object.get("metadata", {}).get("merchant_id")

        # Extract payment method details
        payment_method_type = self._extract_payment_method_type(data_object, event_type)
        card_brand, card_last_four = self._extract_card_details(data_object)

        # Extract status
        status = self._extract_status(data_object, event_type)

        # Extract failure info
        failure_code, failure_message = self._extract_failure_info(data_object)

        # Extract timestamp
        created_timestamp = data_object.get("created") or raw_event.get("created")
        provider_created_at = datetime.fromtimestamp(created_timestamp, tz=timezone.utc)

        # Build unified event
        unified_event = UnifiedPaymentEvent(
            event_id=f"stripe:{event_id}",
            provider="stripe",
            provider_event_id=event_id,
            event_type=normalize_event_type("stripe", event_type),
            merchant_id=normalize_null_string(merchant_id),
            customer_id=customer_id,
            amount_cents=normalized_amount,
            currency=normalized_currency,
            payment_method_type=payment_method_type,
            card_brand=card_brand,
            card_last_four=card_last_four,
            status=status,
            failure_code=failure_code,
            failure_message=failure_message,
            metadata=data_object.get("metadata", {}),
            provider_created_at=provider_created_at,
        )

        return unified_event, result

    def _extract_payment_method_type(self, data_object: dict, event_type: str) -> str | None:
        """Extract payment method type from event data."""
        # Check payment_method_types array (payment_intent)
        method_types = data_object.get("payment_method_types", [])
        if method_types:
            return method_types[0]

        # Check payment_method_details (charge)
        details = data_object.get("payment_method_details", {})
        if details and isinstance(details, dict):
            return details.get("type")

        # For refunds, default to "refund"
        if event_type and event_type.startswith("refund."):
            return "refund"

        return "card"  # Default

    def _extract_card_details(self, data_object: dict) -> tuple[str | None, str | None]:
        """Extract card brand and last four digits."""
        details = data_object.get("payment_method_details", {})
        if not details or not isinstance(details, dict):
            return None, None

        card = details.get("card", {})
        if not card:
            return None, None

        brand = card.get("brand")
        last4 = card.get("last4")
        return brand, last4

    def _extract_status(self, data_object: dict, event_type: str | None) -> str:
        """Extract and normalize status from event data."""
        status = data_object.get("status")
        if status:
            return status

        # Infer from event type if status not present
        if event_type:
            if "succeeded" in event_type:
                return "succeeded"
            if "failed" in event_type:
                return "failed"
            if "canceled" in event_type:
                return "canceled"
            if "pending" in event_type:
                return "pending"
            if "processing" in event_type:
                return "processing"

        return "unknown"

    def _extract_failure_info(self, data_object: dict) -> tuple[str | None, str | None]:
        """Extract failure code and message."""
        # Direct failure fields (charge)
        failure_code = data_object.get("failure_code")
        failure_message = data_object.get("failure_message")

        if failure_code or failure_message:
            return (
                normalize_null_string(failure_code),
                normalize_null_string(failure_message),
            )

        # Check last_payment_error (payment_intent)
        last_error = data_object.get("last_payment_error", {})
        if last_error:
            return (
                normalize_null_string(last_error.get("code")),
                normalize_null_string(last_error.get("message")),
            )

        # Check failure_reason (refund)
        failure_reason = data_object.get("failure_reason")
        if failure_reason:
            return normalize_null_string(failure_reason), None

        return None, None
