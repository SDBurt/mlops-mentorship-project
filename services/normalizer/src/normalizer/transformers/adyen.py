"""Adyen event transformer."""

from datetime import datetime, timezone
from typing import Any

from ..validators import ValidationResult, normalize_null_string
from ..validators.amount import AmountValidator
from ..validators.currency import CurrencyValidator
from .base import UnifiedPaymentEvent, normalize_event_type


class AdyenTransformer:
    """Transforms Adyen webhook events to unified schema."""

    def __init__(self):
        self.currency_validator = CurrencyValidator()
        self.amount_validator = AmountValidator()

    def transform(self, raw_event: dict[str, Any]) -> tuple[UnifiedPaymentEvent | None, ValidationResult]:
        """
        Transform a raw Adyen notification item to unified format.

        Note: Adyen events are pre-processed by the gateway router to extract
        individual notification items. This receives a single item with its
        live flag.

        Args:
            raw_event: Raw Adyen notification item (already unwrapped)

        Returns:
            Tuple of (unified_event, validation_result)
            unified_event is None if validation fails
        """
        result = ValidationResult(is_valid=True)

        # Validate required fields
        psp_reference = raw_event.get("pspReference")
        if not psp_reference:
            result.add_error("pspReference", "MISSING_PSP_REFERENCE", "PSP Reference is required")

        event_code = raw_event.get("eventCode")
        if not event_code:
            result.add_error("eventCode", "MISSING_EVENT_CODE", "Event code is required")

        merchant_account = raw_event.get("merchantAccountCode")
        if not merchant_account:
            result.add_error("merchantAccountCode", "MISSING_MERCHANT_ACCOUNT", "Merchant account is required")

        # Extract and validate amount
        amount_data = raw_event.get("amount", {}) or {}
        amount = amount_data.get("value")
        currency = amount_data.get("currency")

        amount_valid, normalized_amount, amount_error = self.amount_validator.validate(amount)
        if not amount_valid:
            code = "INVALID_AMOUNT"
            if amount is not None:
                if amount < 0:
                    code = "INVALID_AMOUNT_NEGATIVE"
                elif amount > self.amount_validator.max_amount:
                    code = "INVALID_AMOUNT_TOO_LARGE"
            result.add_error("amount.value", code, amount_error or "Invalid amount")

        currency_valid, normalized_currency, currency_error = self.currency_validator.validate(currency)
        if not currency_valid:
            result.add_error("amount.currency", "INVALID_CURRENCY", currency_error or "Invalid currency")

        if not result.is_valid:
            return None, result

        # Extract success flag
        success = raw_event.get("success", False)

        # Determine status based on eventCode and success
        status = self._determine_status(event_code, success)

        # Extract failure info from reason field
        failure_code = None
        failure_message = None
        if not success:
            reason = raw_event.get("reason")
            if reason:
                failure_code = self._extract_failure_code(reason)
                failure_message = reason

        # Extract timestamp
        event_date = raw_event.get("eventDate")
        provider_created_at = self._parse_adyen_timestamp(event_date)

        # Extract payment method
        payment_method = raw_event.get("paymentMethod")
        payment_method_type = self._normalize_payment_method(payment_method)

        # Build unique event ID
        event_id = f"{psp_reference}_{event_code}"

        # Build unified event
        unified_event = UnifiedPaymentEvent(
            event_id=f"adyen:{event_id}",
            provider="adyen",
            provider_event_id=psp_reference,
            event_type=normalize_event_type("adyen", event_code),
            merchant_id=merchant_account,
            customer_id=None,  # Adyen doesn't include customer ID in standard webhooks
            amount_cents=normalized_amount,
            currency=normalized_currency,
            payment_method_type=payment_method_type,
            card_brand=self._extract_card_brand(raw_event),
            card_last_four=self._extract_card_last_four(raw_event),
            status=status,
            failure_code=failure_code,
            failure_message=failure_message,
            metadata={
                "original_reference": raw_event.get("originalReference"),
                "merchant_reference": raw_event.get("merchantReference"),
                "operations": raw_event.get("operations"),
                "live": raw_event.get("live", False),
            },
            provider_created_at=provider_created_at,
        )

        return unified_event, result

    def _determine_status(self, event_code: str, success: bool) -> str:
        """Determine normalized status from event code and success flag."""
        if not success:
            return "failed"

        status_map = {
            "AUTHORISATION": "authorized",
            "CAPTURE": "captured",
            "CANCELLATION": "canceled",
            "REFUND": "refunded",
            "REFUND_FAILED": "refund_failed",
            "CHARGEBACK": "disputed",
            "CHARGEBACK_REVERSED": "dispute_reversed",
            "PENDING": "pending",
        }
        return status_map.get(event_code, event_code.lower())

    def _normalize_payment_method(self, payment_method: str | None) -> str | None:
        """Normalize Adyen payment method to standard format."""
        if not payment_method:
            return None

        # Common Adyen payment method mappings
        method_map = {
            "visa": "card",
            "mc": "card",
            "amex": "card",
            "discover": "card",
            "jcb": "card",
            "diners": "card",
            "cup": "card",  # China UnionPay
            "ideal": "bank_transfer",
            "sepadirectdebit": "bank_account",
            "paypal": "paypal",
            "applepay": "wallet",
            "googlepay": "wallet",
            "klarna": "buy_now_pay_later",
            "afterpay": "buy_now_pay_later",
            "affirm": "buy_now_pay_later",
        }

        return method_map.get(payment_method.lower(), payment_method.lower())

    def _extract_card_brand(self, raw_event: dict[str, Any]) -> str | None:
        """Extract card brand from additional data or payment method."""
        additional_data = raw_event.get("additionalData", {}) or {}

        # Try cardBin first (more reliable)
        card_brand = additional_data.get("cardBin")
        if card_brand:
            return card_brand

        # Fall back to payment method
        payment_method = raw_event.get("paymentMethod")
        if payment_method:
            brand_map = {
                "visa": "visa",
                "mc": "mastercard",
                "amex": "amex",
                "discover": "discover",
                "jcb": "jcb",
                "diners": "diners",
            }
            return brand_map.get(payment_method.lower())

        return None

    def _extract_card_last_four(self, raw_event: dict[str, Any]) -> str | None:
        """Extract last 4 digits of card from additional data."""
        additional_data = raw_event.get("additionalData", {}) or {}
        return additional_data.get("cardSummary")

    def _extract_failure_code(self, reason: str) -> str:
        """Extract a failure code from the reason string."""
        # Common Adyen refusal reasons mapped to codes
        reason_lower = reason.lower()
        if "declined" in reason_lower or "refused" in reason_lower:
            return "declined"
        if "fraud" in reason_lower:
            return "fraud"
        if "expired" in reason_lower:
            return "expired_card"
        if "insufficient" in reason_lower:
            return "insufficient_funds"
        if "invalid" in reason_lower:
            return "invalid_card"
        if "blocked" in reason_lower:
            return "blocked"
        if "cancelled" in reason_lower or "canceled" in reason_lower:
            return "canceled"

        return "unknown"

    def _parse_adyen_timestamp(self, timestamp: str | None) -> datetime:
        """Parse Adyen timestamp format to datetime."""
        if not timestamp:
            return datetime.now(timezone.utc)

        try:
            # Adyen uses ISO 8601 format: "2024-01-15T12:00:00+00:00"
            if timestamp.endswith("Z"):
                timestamp = timestamp[:-1] + "+00:00"
            return datetime.fromisoformat(timestamp)
        except (ValueError, TypeError):
            return datetime.now(timezone.utc)
