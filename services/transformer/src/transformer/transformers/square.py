"""Square event transformer."""

from datetime import datetime, timezone
from typing import Any

from ..validators import ValidationResult, normalize_null_string
from ..validators.amount import AmountValidator
from ..validators.currency import CurrencyValidator
from .base import UnifiedPaymentEvent, normalize_event_type


class SquareTransformer:
    """Transforms Square webhook events to unified schema."""

    def __init__(self):
        self.currency_validator = CurrencyValidator()
        self.amount_validator = AmountValidator()

    def transform(self, raw_event: dict[str, Any]) -> tuple[UnifiedPaymentEvent | None, ValidationResult]:
        """
        Transform a raw Square event to unified format.

        Args:
            raw_event: Raw Square webhook event

        Returns:
            Tuple of (unified_event, validation_result)
            unified_event is None if validation fails
        """
        result = ValidationResult(is_valid=True)

        # Validate required top-level fields
        event_id = raw_event.get("event_id")
        if not event_id:
            result.add_error("event_id", "MISSING_EVENT_ID", "Event ID is required")

        event_type = raw_event.get("type")
        if not event_type:
            result.add_error("type", "MISSING_EVENT_TYPE", "Event type is required")

        merchant_id = raw_event.get("merchant_id")

        # Get nested data
        data = raw_event.get("data", {})
        if not data:
            result.add_error("data", "MISSING_DATA", "Data object is required")
            return None, result

        # Get the actual payment/refund object from data.object
        data_object = data.get("object", {})
        object_type = data.get("type", "")

        # Extract the nested payment or refund data
        if object_type == "payment":
            payment_data = data_object.get("payment", {})
            if not payment_data:
                result.add_error("data.object.payment", "MISSING_PAYMENT", "Payment object is required")
                return None, result
            return self._transform_payment(raw_event, event_id, event_type, merchant_id, payment_data, result)
        elif object_type == "refund":
            refund_data = data_object.get("refund", {})
            if not refund_data:
                result.add_error("data.object.refund", "MISSING_REFUND", "Refund object is required")
                return None, result
            return self._transform_refund(raw_event, event_id, event_type, merchant_id, refund_data, result)
        else:
            # Unknown object type - try to extract payment/refund from object
            payment_data = data_object.get("payment")
            if payment_data:
                return self._transform_payment(raw_event, event_id, event_type, merchant_id, payment_data, result)
            refund_data = data_object.get("refund")
            if refund_data:
                return self._transform_refund(raw_event, event_id, event_type, merchant_id, refund_data, result)

            result.add_error("data.type", "UNKNOWN_OBJECT_TYPE", f"Unknown object type: {object_type}")
            return None, result

    def _transform_payment(
        self,
        raw_event: dict[str, Any],
        event_id: str,
        event_type: str,
        merchant_id: str | None,
        payment_data: dict[str, Any],
        result: ValidationResult,
    ) -> tuple[UnifiedPaymentEvent | None, ValidationResult]:
        """Transform a Square payment event."""
        object_id = payment_data.get("id")
        if not object_id:
            result.add_error("payment.id", "MISSING_OBJECT_ID", "Payment ID is required")

        # Extract amount from amount_money
        amount_money = payment_data.get("amount_money", {})
        amount = amount_money.get("amount")
        currency = amount_money.get("currency")

        # Validate amount
        amount_valid, normalized_amount, amount_error = self.amount_validator.validate(amount)
        if not amount_valid:
            code = "INVALID_AMOUNT_NEGATIVE" if amount is not None and amount < 0 else "INVALID_AMOUNT"
            if amount is not None and amount > self.amount_validator.max_amount:
                code = "INVALID_AMOUNT_TOO_LARGE"
            result.add_error("payment.amount_money.amount", code, amount_error or "Invalid amount")

        # Validate currency
        currency_valid, normalized_currency, currency_error = self.currency_validator.validate(currency)
        if not currency_valid:
            result.add_error("payment.amount_money.currency", "INVALID_CURRENCY", currency_error or "Invalid currency")

        if not result.is_valid:
            return None, result

        # Extract customer info
        customer_id = normalize_null_string(payment_data.get("customer_id"))

        # Extract card details if present
        card_details = payment_data.get("card_details", {}) or {}
        card_brand = normalize_null_string(card_details.get("card_brand"))
        card_last_four = normalize_null_string(card_details.get("last_4"))

        # Extract payment method type
        source_type = payment_data.get("source_type", "CARD")
        payment_method_type = self._normalize_source_type(source_type)

        # Extract status
        status = self._normalize_status(payment_data.get("status", ""))

        # Extract timestamp
        created_at = payment_data.get("created_at") or raw_event.get("created_at")
        provider_created_at = self._parse_iso_timestamp(created_at)

        # Build unified event
        unified_event = UnifiedPaymentEvent(
            event_id=f"square:{event_id}",
            provider="square",
            provider_event_id=event_id,
            event_type=normalize_event_type("square", event_type),
            merchant_id=normalize_null_string(merchant_id),
            customer_id=customer_id,
            amount_cents=normalized_amount,
            currency=normalized_currency,
            payment_method_type=payment_method_type,
            card_brand=card_brand,
            card_last_four=card_last_four,
            status=status,
            failure_code=None,  # Square doesn't expose failure codes the same way
            failure_message=None,
            metadata={
                "location_id": payment_data.get("location_id"),
                "order_id": payment_data.get("order_id"),
                "reference_id": payment_data.get("reference_id"),
            },
            provider_created_at=provider_created_at,
        )

        return unified_event, result

    def _transform_refund(
        self,
        raw_event: dict[str, Any],
        event_id: str,
        event_type: str,
        merchant_id: str | None,
        refund_data: dict[str, Any],
        result: ValidationResult,
    ) -> tuple[UnifiedPaymentEvent | None, ValidationResult]:
        """Transform a Square refund event."""
        object_id = refund_data.get("id")
        if not object_id:
            result.add_error("refund.id", "MISSING_OBJECT_ID", "Refund ID is required")

        # Extract amount from amount_money
        amount_money = refund_data.get("amount_money", {})
        amount = amount_money.get("amount")
        currency = amount_money.get("currency")

        # Validate amount
        amount_valid, normalized_amount, amount_error = self.amount_validator.validate(amount)
        if not amount_valid:
            code = "INVALID_AMOUNT"
            result.add_error("refund.amount_money.amount", code, amount_error or "Invalid amount")

        # Validate currency
        currency_valid, normalized_currency, currency_error = self.currency_validator.validate(currency)
        if not currency_valid:
            result.add_error("refund.amount_money.currency", "INVALID_CURRENCY", currency_error or "Invalid currency")

        if not result.is_valid:
            return None, result

        # Extract status
        status = self._normalize_refund_status(refund_data.get("status", ""))

        # Extract timestamp
        created_at = refund_data.get("created_at") or raw_event.get("created_at")
        provider_created_at = self._parse_iso_timestamp(created_at)

        # Build unified event
        unified_event = UnifiedPaymentEvent(
            event_id=f"square:{event_id}",
            provider="square",
            provider_event_id=event_id,
            event_type=normalize_event_type("square", event_type),
            merchant_id=normalize_null_string(merchant_id),
            customer_id=None,  # Refunds don't have direct customer reference
            amount_cents=normalized_amount,
            currency=normalized_currency,
            payment_method_type="refund",
            card_brand=None,
            card_last_four=None,
            status=status,
            failure_code=None,
            failure_message=None,
            metadata={
                "location_id": refund_data.get("location_id"),
                "payment_id": refund_data.get("payment_id"),
                "reason": refund_data.get("reason"),
            },
            provider_created_at=provider_created_at,
        )

        return unified_event, result

    def _normalize_source_type(self, source_type: str | None) -> str:
        """Normalize Square source type to payment method type."""
        if not source_type:
            return "card"
        source_map = {
            "CARD": "card",
            "CARD_ON_FILE": "card",
            "CASH": "cash",
            "EXTERNAL": "external",
            "WALLET": "wallet",
            "BANK_ACCOUNT": "bank_account",
            "BUY_NOW_PAY_LATER": "buy_now_pay_later",
            "SQUARE_ACCOUNT": "square_account",
        }
        return source_map.get(source_type.upper(), source_type.lower())

    def _normalize_status(self, status: str) -> str:
        """Normalize Square payment status."""
        status_map = {
            "APPROVED": "approved",
            "COMPLETED": "succeeded",
            "CANCELED": "canceled",
            "FAILED": "failed",
            "PENDING": "pending",
        }
        return status_map.get(status.upper(), status.lower())

    def _normalize_refund_status(self, status: str) -> str:
        """Normalize Square refund status."""
        status_map = {
            "PENDING": "pending",
            "COMPLETED": "succeeded",
            "REJECTED": "rejected",
            "FAILED": "failed",
        }
        return status_map.get(status.upper(), status.lower())

    def _parse_iso_timestamp(self, timestamp: str | None) -> datetime:
        """Parse ISO 8601 timestamp to datetime."""
        if not timestamp:
            return datetime.now(timezone.utc)
        try:
            # Handle Z suffix
            if timestamp.endswith("Z"):
                timestamp = timestamp[:-1] + "+00:00"
            return datetime.fromisoformat(timestamp)
        except (ValueError, TypeError):
            return datetime.now(timezone.utc)
