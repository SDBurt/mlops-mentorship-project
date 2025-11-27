# temporal/providers/square.py
"""
Square payment provider implementation.

Generates realistic Square Payment-like objects and normalizes them
for workflow processing.

Reference: https://developer.squareup.com/reference/square/payments-api/create-payment
"""
import random
import string
from datetime import datetime

from temporal.providers.base import (
    PaymentProvider, NormalizedPayment, FailedPaymentEvent, FailureCode, Provider
)


class SquareProvider(PaymentProvider):
    """Square payment generator with realistic Payment structure."""

    # Card brand distribution
    CARD_BRANDS = ["VISA"] * 50 + ["MASTERCARD"] * 30 + ["AMERICAN_EXPRESS"] * 15 + ["DISCOVER"] * 5

    # Currency distribution (Square supports fewer currencies)
    CURRENCIES = ["USD"] * 80 + ["CAD"] * 15 + ["GBP"] * 5

    # Amount ranges (in cents)
    AMOUNT_RANGES = {
        "USD": (500, 100000),
        "CAD": (600, 120000),
        "GBP": (400, 80000),
    }

    # Sample Square merchants (location-based businesses)
    MERCHANTS = [
        {"name": "Blue Bottle Coffee", "mcc": "5812", "category": "restaurant"},
        {"name": "Sweetgreen", "mcc": "5812", "category": "restaurant"},
        {"name": "Warby Parker", "mcc": "5944", "category": "retail"},
        {"name": "Glossier", "mcc": "5977", "category": "beauty"},
        {"name": "Allbirds", "mcc": "5661", "category": "retail"},
        {"name": "Shake Shack", "mcc": "5812", "category": "restaurant"},
        {"name": "SoulCycle", "mcc": "7941", "category": "fitness"},
        {"name": "Peloton", "mcc": "5941", "category": "fitness"},
        {"name": "Casper", "mcc": "5712", "category": "retail"},
        {"name": "WeWork", "mcc": "6513", "category": "real_estate"},
    ]

    # US locations
    LOCATIONS = [
        {"city": "New York", "state": "NY", "country": "US"},
        {"city": "San Francisco", "state": "CA", "country": "US"},
        {"city": "Los Angeles", "state": "CA", "country": "US"},
        {"city": "Chicago", "state": "IL", "country": "US"},
        {"city": "Austin", "state": "TX", "country": "US"},
        {"city": "Seattle", "state": "WA", "country": "US"},
        {"city": "Miami", "state": "FL", "country": "US"},
        {"city": "Denver", "state": "CO", "country": "US"},
    ]

    # Names
    FIRST_NAMES = ["Alex", "Taylor", "Jordan", "Casey", "Morgan", "Riley",
                   "Quinn", "Avery", "Parker", "Cameron"]
    LAST_NAMES = ["Anderson", "Thompson", "White", "Harris", "Martin", "Jackson",
                  "Clark", "Lewis", "Walker", "Hall"]

    def get_provider_name(self) -> str:
        return Provider.SQUARE.value

    def _generate_id(self, length: int = 22) -> str:
        """Generate Square-style alphanumeric ID."""
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choices(chars, k=length))

    # Square failure codes with realistic distribution
    FAILURE_CODES = [
        ("GENERIC_DECLINE", 35),
        ("INSUFFICIENT_FUNDS", 25),
        ("CARD_EXPIRED", 15),
        ("CVV_FAILURE", 10),
        ("INVALID_ACCOUNT", 8),
        ("TRANSACTION_LIMIT", 5),
        ("VOICE_FAILURE", 2),
    ]

    FAILURE_MESSAGES = {
        "GENERIC_DECLINE": "Card declined by issuer.",
        "INSUFFICIENT_FUNDS": "Insufficient funds in account.",
        "CARD_EXPIRED": "Card has expired.",
        "CVV_FAILURE": "CVV verification failed.",
        "INVALID_ACCOUNT": "Invalid card number.",
        "TRANSACTION_LIMIT": "Transaction exceeds card limit.",
        "VOICE_FAILURE": "Voice authorization required.",
    }

    def generate_payment(self) -> NormalizedPayment:
        """Generate a Square Payment and normalize it."""
        square_payment = self._generate_square_payment()
        return self._normalize(square_payment)

    def generate_failed_payment(self, failure_code: str | None = None) -> FailedPaymentEvent:
        """
        Generate a failed payment event from Square.

        Args:
            failure_code: Optional specific failure code. If None, randomly selected.

        Returns:
            FailedPaymentEvent with Square-specific failure details
        """
        payment = self.generate_payment()

        if failure_code is None:
            codes = []
            for code, weight in self.FAILURE_CODES:
                codes.extend([code] * weight)
            failure_code = random.choice(codes)

        normalized_failure = FailureCode.SQUARE_MAPPING.get(
            failure_code, FailureCode.CARD_DECLINED
        )

        original_charge_id = self._generate_id()

        return FailedPaymentEvent(
            payment=payment,
            failure_code=normalized_failure,
            failure_message=self.FAILURE_MESSAGES.get(
                failure_code, "Payment declined."
            ),
            failure_timestamp=datetime.utcnow().isoformat() + "Z",
            original_charge_id=original_charge_id,
            retry_count=0,
        )

    def _generate_square_payment(self) -> dict:
        """Generate raw Square Payment object."""
        brand = random.choice(self.CARD_BRANDS)
        currency = random.choice(self.CURRENCIES)
        min_amt, max_amt = self.AMOUNT_RANGES.get(currency, (500, 100000))
        amount = random.randint(min_amt, max_amt)

        merchant = random.choice(self.MERCHANTS)
        location = random.choice(self.LOCATIONS)

        first_name = random.choice(self.FIRST_NAMES)
        last_name = random.choice(self.LAST_NAMES)

        # Square statuses
        status = random.choices(
            ["COMPLETED", "APPROVED", "PENDING", "FAILED"],
            weights=[70, 15, 10, 5]
        )[0]

        card_status = "CAPTURED" if status == "COMPLETED" else (
            "AUTHORIZED" if status == "APPROVED" else "FAILED"
        )

        return {
            # Square Payment fields
            "id": self._generate_id(),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "amount_money": {
                "amount": amount,
                "currency": currency
            },
            "total_money": {
                "amount": amount,
                "currency": currency
            },
            "status": status,
            "delay_duration": "PT168H",
            "delay_action": "CANCEL",
            "source_type": "CARD",
            "location_id": f"L{self._generate_id(12)}",
            "order_id": f"O{self._generate_id(16)}",
            "reference_id": f"REF-{random.randint(100000, 999999)}",

            # Card details (Square structure)
            "card_details": {
                "status": card_status,
                "card": {
                    "card_brand": brand,
                    "last_4": str(random.randint(1000, 9999)),
                    "exp_month": random.randint(1, 12),
                    "exp_year": random.randint(2025, 2030),
                    "cardholder_name": f"{first_name} {last_name}",
                    "fingerprint": self._generate_id(16),
                    "card_type": random.choice(["CREDIT", "DEBIT"]),
                    "prepaid_type": random.choice(["NOT_PREPAID", "NOT_PREPAID", "PREPAID"]),
                    "bin": str(random.randint(400000, 599999)),
                },
                "entry_method": random.choice(["KEYED", "EMV", "CONTACTLESS_NFC", "SWIPED"]),
                "cvv_status": random.choice(["CVV_ACCEPTED", "CVV_ACCEPTED", "CVV_REJECTED"]),
                "avs_status": random.choice(["AVS_ACCEPTED", "AVS_ACCEPTED", "AVS_REJECTED"]),
                "auth_result_code": self._generate_id(6),
            },

            # Buyer information
            "buyer_email_address": f"{first_name.lower()}.{last_name.lower()}@example.com",
            "billing_address": {
                "address_line_1": f"{random.randint(100, 9999)} {random.choice(['Main', 'Oak', 'Pine', 'Market'])} St",
                "address_line_2": random.choice([None, None, f"Suite {random.randint(100, 500)}"]),
                "locality": location["city"],
                "administrative_district_level_1": location["state"],
                "postal_code": f"{random.randint(10000, 99999)}",
                "country": location["country"],
            },

            # Merchant/location info
            "merchant_data": {
                "name": merchant["name"],
                "mcc": merchant["mcc"],
                "category": merchant["category"],
                "location": location,
            },

            # Receipt
            "receipt_number": f"R{self._generate_id(8)}",
            "receipt_url": f"https://squareup.com/receipt/preview/{self._generate_id(32)}",

            # Version control
            "version_token": self._generate_id(32),
        }

    def _normalize(self, square_payment: dict) -> NormalizedPayment:
        """Convert Square Payment to normalized format."""
        card = square_payment["card_details"]["card"]
        card_details = square_payment["card_details"]
        billing = square_payment.get("billing_address", {})
        merchant = square_payment["merchant_data"]
        amount_money = square_payment["amount_money"]

        return NormalizedPayment(
            # Provider identification
            provider=self.get_provider_name(),
            provider_payment_id=square_payment["id"],

            # Transaction details
            amount_cents=amount_money["amount"],
            currency=amount_money["currency"],

            # Customer information
            customer_id=f"sqcust_{square_payment['id'][:12]}",  # Square doesn't always have customer IDs
            customer_email=square_payment.get("buyer_email_address", ""),
            customer_name=card.get("cardholder_name", "Unknown"),

            # Card details
            card_brand=self._normalize_card_brand(card["card_brand"]),
            card_last4=card["last_4"],
            card_exp_month=card["exp_month"],
            card_exp_year=card["exp_year"],
            card_funding=card.get("card_type", "unknown").lower(),

            # Merchant information
            merchant_name=merchant["name"],
            merchant_category=merchant["category"],
            merchant_mcc=merchant["mcc"],

            # Billing address
            billing_address={
                "line1": billing.get("address_line_1", ""),
                "line2": billing.get("address_line_2"),
                "city": billing.get("locality", ""),
                "state": billing.get("administrative_district_level_1", ""),
                "postal_code": billing.get("postal_code", ""),
                "country": billing.get("country", "US"),
            },

            # Fraud signals (normalized)
            fraud_signals={
                "cvc_check": self._normalize_check_status(card_details.get("cvv_status")),
                "avs_check": self._normalize_check_status(card_details.get("avs_status")),
                "postal_check": self._normalize_check_status(card_details.get("avs_status")),  # Square combines
                "risk_level": "unknown",
            },

            # Metadata
            metadata={
                "order_id": square_payment.get("order_id", ""),
                "reference_id": square_payment.get("reference_id", ""),
                "receipt_number": square_payment.get("receipt_number", ""),
                "location_id": square_payment.get("location_id", ""),
            },
            created_at=square_payment["created_at"],

            # Raw data for debugging
            raw_provider_data=square_payment,
        )
