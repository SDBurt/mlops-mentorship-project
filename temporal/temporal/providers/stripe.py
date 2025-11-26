# temporal/providers/stripe.py
"""
Stripe payment provider implementation.

Generates realistic Stripe PaymentIntent-like objects and normalizes them
for workflow processing.

Reference: https://stripe.com/docs/api/payment_intents/object
"""
import random
import string
import time
from datetime import datetime

from temporal.providers.base import PaymentProvider, NormalizedPayment, Provider


class StripeProvider(PaymentProvider):
    """Stripe payment generator with realistic PaymentIntent structure."""

    # Card brand distribution (weighted towards Visa)
    CARD_BRANDS = ["visa"] * 50 + ["mastercard"] * 30 + ["amex"] * 15 + ["discover"] * 5
    CARD_PREFIXES = {"visa": "4", "mastercard": "5", "amex": "3", "discover": "6"}

    # Currency distribution (weighted towards USD)
    CURRENCIES = ["usd"] * 70 + ["eur"] * 15 + ["gbp"] * 10 + ["cad"] * 5

    # Amount ranges by currency (in cents)
    AMOUNT_RANGES = {
        "usd": (500, 100000),
        "eur": (500, 100000),
        "gbp": (400, 80000),
        "cad": (600, 120000),
    }

    # Sample merchants
    MERCHANTS = [
        {"name": "Netflix", "mcc": "4899", "category": "streaming"},
        {"name": "Spotify", "mcc": "5815", "category": "digital_goods"},
        {"name": "Adobe Creative Cloud", "mcc": "5734", "category": "software"},
        {"name": "Microsoft 365", "mcc": "5734", "category": "software"},
        {"name": "Dropbox", "mcc": "7372", "category": "cloud_storage"},
        {"name": "Slack Technologies", "mcc": "7372", "category": "saas"},
        {"name": "Zoom Communications", "mcc": "4814", "category": "telecom"},
        {"name": "GitHub", "mcc": "7372", "category": "developer_tools"},
        {"name": "AWS", "mcc": "7372", "category": "cloud_infrastructure"},
        {"name": "Heroku", "mcc": "7372", "category": "cloud_platform"},
    ]

    # US states and cities
    STATES = ["CA", "NY", "TX", "FL", "WA", "IL", "PA", "OH", "GA", "NC"]
    CITIES = {
        "CA": ["San Francisco", "Los Angeles", "San Diego"],
        "NY": ["New York", "Brooklyn", "Buffalo"],
        "TX": ["Austin", "Houston", "Dallas"],
        "FL": ["Miami", "Orlando", "Tampa"],
        "WA": ["Seattle", "Bellevue", "Tacoma"],
    }

    # Names
    FIRST_NAMES = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer",
                   "Michael", "Linda", "David", "Elizabeth"]
    LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
                  "Miller", "Davis", "Rodriguez", "Martinez"]

    def get_provider_name(self) -> str:
        return Provider.STRIPE.value

    def _generate_id(self, prefix: str, length: int = 24) -> str:
        """Generate Stripe-style ID (e.g., pi_ABC123...)."""
        chars = string.ascii_letters + string.digits
        return f"{prefix}_{''.join(random.choices(chars, k=length))}"

    def generate_payment(self) -> NormalizedPayment:
        """Generate a Stripe PaymentIntent and normalize it."""
        # Generate raw Stripe data
        stripe_payment = self._generate_stripe_payment()

        # Normalize to common schema
        return self._normalize(stripe_payment)

    def _generate_stripe_payment(self) -> dict:
        """Generate raw Stripe PaymentIntent object."""
        brand = random.choice(self.CARD_BRANDS)
        last4 = f"{self.CARD_PREFIXES[brand]}{random.randint(100, 999)}"
        currency = random.choice(self.CURRENCIES)
        min_amt, max_amt = self.AMOUNT_RANGES.get(currency, (500, 100000))
        amount = random.randint(min_amt, max_amt)

        customer_id = self._generate_id("cus")
        payment_method_id = self._generate_id("pm")
        payment_intent_id = self._generate_id("pi")

        merchant = random.choice(self.MERCHANTS)
        state = random.choice(self.STATES)
        city = random.choice(self.CITIES.get(state, ["Springfield"]))

        first_name = random.choice(self.FIRST_NAMES)
        last_name = random.choice(self.LAST_NAMES)

        now = int(time.time())

        return {
            # Stripe PaymentIntent fields
            "id": payment_intent_id,
            "object": "payment_intent",
            "amount": amount,
            "amount_received": 0,
            "currency": currency,
            "customer": customer_id,
            "payment_method": payment_method_id,
            "status": "requires_capture",
            "capture_method": "automatic",
            "confirmation_method": "automatic",
            "created": now,
            "livemode": False,

            # Payment method details
            "payment_method_details": {
                "type": "card",
                "card": {
                    "brand": brand,
                    "last4": last4,
                    "exp_month": random.randint(1, 12),
                    "exp_year": random.randint(2025, 2030),
                    "funding": random.choice(["credit", "debit"]),
                    "country": "US",
                    "fingerprint": self._generate_id("fp", 16),
                    "checks": {
                        "cvc_check": "pass",
                        "address_postal_code_check": random.choice(["pass", "pass", "pass", "fail"]),
                        "address_line1_check": random.choice(["pass", "pass", "unavailable"]),
                    }
                }
            },

            # Billing details
            "billing_details": {
                "name": f"{first_name} {last_name}",
                "email": f"{first_name.lower()}.{last_name.lower()}@example.com",
                "phone": f"+1{random.randint(2000000000, 9999999999)}",
                "address": {
                    "line1": f"{random.randint(100, 9999)} {random.choice(['Main', 'Oak', 'Pine', 'Maple', 'Cedar'])} {random.choice(['St', 'Ave', 'Blvd', 'Dr'])}",
                    "line2": random.choice([None, None, None, f"Apt {random.randint(1, 500)}"]),
                    "city": city,
                    "state": state,
                    "postal_code": f"{random.randint(10000, 99999)}",
                    "country": "US"
                }
            },

            # Merchant info
            "statement_descriptor": merchant["name"][:22],
            "statement_descriptor_suffix": None,
            "merchant_data": {
                "name": merchant["name"],
                "mcc": merchant["mcc"],
                "category": merchant["category"],
            },

            # Metadata
            "metadata": {
                "subscription_id": self._generate_id("sub"),
                "invoice_id": self._generate_id("in"),
                "order_id": f"ORD-{random.randint(100000, 999999)}",
                "customer_tier": random.choice(["free", "pro", "enterprise"]),
                "billing_cycle": random.choice(["monthly", "annual"]),
            },

            # Risk signals (to be populated by fraud check)
            "risk_score": None,
            "risk_level": None,

            # Timestamps
            "processing_timestamps": {
                "submitted_at": datetime.utcnow().isoformat() + "Z",
                "authorized_at": None,
                "captured_at": None,
            }
        }

    def _normalize(self, stripe_payment: dict) -> NormalizedPayment:
        """Convert Stripe PaymentIntent to normalized format."""
        card = stripe_payment["payment_method_details"]["card"]
        billing = stripe_payment["billing_details"]
        merchant = stripe_payment["merchant_data"]
        checks = card.get("checks", {})

        return NormalizedPayment(
            # Provider identification
            provider=self.get_provider_name(),
            provider_payment_id=stripe_payment["id"],

            # Transaction details
            amount_cents=stripe_payment["amount"],
            currency=stripe_payment["currency"].upper(),

            # Customer information
            customer_id=stripe_payment["customer"],
            customer_email=billing["email"],
            customer_name=billing["name"],

            # Card details
            card_brand=self._normalize_card_brand(card["brand"]),
            card_last4=card["last4"],
            card_exp_month=card["exp_month"],
            card_exp_year=card["exp_year"],
            card_funding=card.get("funding", "unknown"),

            # Merchant information
            merchant_name=merchant["name"],
            merchant_category=merchant["category"],
            merchant_mcc=merchant["mcc"],

            # Billing address
            billing_address={
                "line1": billing["address"]["line1"],
                "line2": billing["address"].get("line2"),
                "city": billing["address"]["city"],
                "state": billing["address"]["state"],
                "postal_code": billing["address"]["postal_code"],
                "country": billing["address"]["country"],
            },

            # Fraud signals (normalized)
            fraud_signals={
                "cvc_check": self._normalize_check_status(checks.get("cvc_check")),
                "avs_check": self._normalize_check_status(checks.get("address_line1_check")),
                "postal_check": self._normalize_check_status(checks.get("address_postal_code_check")),
                "risk_level": "unknown",  # Will be set by fraud check activity
            },

            # Metadata
            metadata=stripe_payment.get("metadata", {}),
            created_at=stripe_payment["processing_timestamps"]["submitted_at"],

            # Raw data for debugging
            raw_provider_data=stripe_payment,
        )
