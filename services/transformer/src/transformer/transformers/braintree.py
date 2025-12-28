"""Braintree event transformer."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from ..validators import ValidationResult
from ..validators.amount import AmountValidator
from ..validators.currency import CurrencyValidator
from .base import UnifiedPaymentEvent, normalize_event_type


class BraintreeTransformer:
    """Transforms Braintree webhook notifications to unified schema."""

    def __init__(self):
        self.currency_validator = CurrencyValidator()
        self.amount_validator = AmountValidator()

    def transform(self, raw_event: dict[str, Any]) -> tuple[UnifiedPaymentEvent | None, ValidationResult]:
        """
        Transform a raw Braintree notification to unified format.

        Args:
            raw_event: Parsed Braintree notification data

        Returns:
            Tuple of (unified_event, validation_result)
            unified_event is None if validation fails
        """
        result = ValidationResult(is_valid=True)

        # Validate required fields
        kind = raw_event.get("kind")
        if not kind:
            result.add_error("kind", "MISSING_KIND", "Notification kind is required")

        timestamp = raw_event.get("timestamp")

        # Get transaction data if present
        transaction = raw_event.get("transaction", {}) or {}
        transaction_id = transaction.get("id")

        # For transaction notifications, we need transaction data
        if kind and kind.startswith("transaction_") and not transaction_id:
            result.add_error("transaction.id", "MISSING_TRANSACTION_ID", "Transaction ID is required for transaction notifications")

        # Extract and validate amount (from transaction)
        amount_str = transaction.get("amount")
        currency = transaction.get("currency_iso_code", "USD")

        if amount_str:
            try:
                # Convert decimal string to cents
                amount_decimal = Decimal(amount_str)
                amount_cents = int(amount_decimal * 100)
            except (ValueError, TypeError, InvalidOperation):
                amount_cents = None
                result.add_error("transaction.amount", "INVALID_AMOUNT", f"Invalid amount format: {amount_str}")
        else:
            amount_cents = 0  # Default for non-transaction events

        # Validate amount if we have one
        if amount_cents is not None and amount_cents > 0:
            amount_valid, normalized_amount, amount_error = self.amount_validator.validate(amount_cents)
            if not amount_valid:
                result.add_error("transaction.amount", "INVALID_AMOUNT", amount_error or "Invalid amount")
            else:
                amount_cents = normalized_amount

        # Validate currency
        currency_valid, normalized_currency, currency_error = self.currency_validator.validate(currency)
        if not currency_valid:
            result.add_error("transaction.currency_iso_code", "INVALID_CURRENCY", currency_error or "Invalid currency")

        if not result.is_valid:
            return None, result

        # Build event ID
        event_id = f"{kind}_{transaction_id}" if transaction_id else f"{kind}_{timestamp}"

        # Extract card details
        card_details = transaction.get("card_details", {}) or {}
        card_brand = card_details.get("card_type")
        card_last_four = card_details.get("last_4")

        # Determine status
        status = self._determine_status(kind, transaction.get("status"))

        # Extract failure info
        failure_code = None
        failure_message = None
        if status == "failed":
            failure_code = transaction.get("status", "unknown")
            failure_message = f"Transaction {transaction.get('status', 'failed')}"

        # Extract payment method type
        payment_method_type = self._normalize_payment_method(
            transaction.get("payment_instrument_type")
        )

        # Parse timestamp
        provider_created_at = self._parse_timestamp(timestamp)

        # Build unified event
        unified_event = UnifiedPaymentEvent(
            event_id=f"braintree:{event_id}",
            provider="braintree",
            provider_event_id=transaction_id or event_id,
            event_type=normalize_event_type("braintree", kind),
            merchant_id=transaction.get("merchant_account_id"),
            customer_id=transaction.get("customer_id"),
            amount_cents=amount_cents or 0,
            currency=normalized_currency,
            payment_method_type=payment_method_type,
            card_brand=self._normalize_card_brand(card_brand),
            card_last_four=card_last_four,
            status=status,
            failure_code=failure_code,
            failure_message=failure_message,
            metadata={
                "kind": kind,
                "transaction_type": transaction.get("type"),
                "subscription": raw_event.get("subscription"),
                "dispute": raw_event.get("dispute"),
                "dev_mode": raw_event.get("dev_mode", False),
            },
            provider_created_at=provider_created_at,
        )

        return unified_event, result

    def _determine_status(self, kind: str, transaction_status: str | None) -> str:
        """Determine normalized status from notification kind and transaction status."""
        # Map Braintree notification kinds to statuses
        kind_status_map = {
            "transaction_settled": "settled",
            "transaction_settlement_declined": "settlement_declined",
            "transaction_disbursed": "disbursed",
            "subscription_charged_successfully": "succeeded",
            "subscription_charged_unsuccessfully": "failed",
            "subscription_canceled": "canceled",
            "dispute_opened": "disputed",
            "dispute_won": "dispute_won",
            "dispute_lost": "dispute_lost",
            "disbursement": "disbursed",
        }

        if kind in kind_status_map:
            return kind_status_map[kind]

        # Fall back to transaction status if available
        if transaction_status:
            status_map = {
                "authorized": "authorized",
                "submitted_for_settlement": "pending",
                "settling": "pending",
                "settled": "settled",
                "voided": "canceled",
                "processor_declined": "failed",
                "gateway_rejected": "failed",
                "failed": "failed",
                "settlement_declined": "settlement_declined",
            }
            return status_map.get(transaction_status.lower(), transaction_status.lower())

        return kind.replace("_", " ").lower() if kind else "unknown"

    def _normalize_payment_method(self, payment_instrument_type: str | None) -> str | None:
        """Normalize Braintree payment instrument type."""
        if not payment_instrument_type:
            return None

        method_map = {
            "credit_card": "card",
            "paypal_account": "paypal",
            "venmo_account": "venmo",
            "apple_pay_card": "wallet",
            "google_pay_card": "wallet",
            "android_pay_card": "wallet",
            "samsung_pay_card": "wallet",
            "visa_checkout_card": "wallet",
            "masterpass_card": "wallet",
            "us_bank_account": "bank_account",
            "sepa_debit_account": "bank_account",
            "local_payment": "local_payment",
        }

        return method_map.get(payment_instrument_type.lower(), payment_instrument_type.lower())

    def _normalize_card_brand(self, card_type: str | None) -> str | None:
        """Normalize card brand to standard format."""
        if not card_type:
            return None

        brand_map = {
            "visa": "visa",
            "mastercard": "mastercard",
            "american express": "amex",
            "amex": "amex",
            "discover": "discover",
            "jcb": "jcb",
            "diners club": "diners",
            "maestro": "maestro",
            "unionpay": "unionpay",
        }

        return brand_map.get(card_type.lower(), card_type.lower())

    def _parse_timestamp(self, timestamp: str | None) -> datetime:
        """Parse timestamp to datetime."""
        if not timestamp:
            return datetime.now(timezone.utc)

        try:
            # Handle ISO 8601 format
            if timestamp.endswith("Z"):
                timestamp = timestamp[:-1] + "+00:00"
            return datetime.fromisoformat(timestamp)
        except (ValueError, TypeError):
            return datetime.now(timezone.utc)
