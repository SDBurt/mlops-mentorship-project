# temporal/providers/braintree.py
"""
Braintree payment provider implementation.

Generates realistic Braintree Transaction-like objects and normalizes them
for workflow processing.

Reference: https://developer.paypal.com/braintree/docs/reference/response/transaction
"""
import random
import string
from datetime import datetime
from decimal import Decimal

from temporal.providers.base import (
    PaymentProvider, NormalizedPayment, FailedPaymentEvent, FailureCode, Provider
)


class BraintreeProvider(PaymentProvider):
    """Braintree payment generator with realistic Transaction structure."""

    # Card brand distribution (Braintree uses mixed case)
    CARD_BRANDS = ["Visa"] * 50 + ["MasterCard"] * 30 + ["American Express"] * 15 + ["Discover"] * 5

    # Currency distribution
    CURRENCIES = ["USD"] * 70 + ["EUR"] * 15 + ["GBP"] * 10 + ["AUD"] * 5

    # Amount ranges (Braintree uses decimal dollars, we'll convert to cents)
    AMOUNT_RANGES = {
        "USD": (5.00, 1000.00),
        "EUR": (5.00, 1000.00),
        "GBP": (4.00, 800.00),
        "AUD": (7.00, 1500.00),
    }

    # Sample Braintree merchants (subscription/enterprise focused)
    MERCHANTS = [
        {"name": "Uber Technologies", "mcc": "4121", "category": "transportation"},
        {"name": "Airbnb", "mcc": "7011", "category": "lodging"},
        {"name": "DoorDash", "mcc": "5812", "category": "delivery"},
        {"name": "Instacart", "mcc": "5411", "category": "grocery"},
        {"name": "Lyft", "mcc": "4121", "category": "transportation"},
        {"name": "Grubhub", "mcc": "5812", "category": "delivery"},
        {"name": "Twilio", "mcc": "4814", "category": "telecom"},
        {"name": "Shopify", "mcc": "5734", "category": "software"},
        {"name": "Stripe Atlas", "mcc": "7372", "category": "software"},
        {"name": "Coinbase", "mcc": "6051", "category": "crypto"},
    ]

    # Names
    FIRST_NAMES = ["Emma", "Liam", "Olivia", "Noah", "Ava", "William",
                   "Sophia", "James", "Isabella", "Oliver"]
    LAST_NAMES = ["Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Lee",
                  "Robinson", "Young", "King", "Wright"]

    def get_provider_name(self) -> str:
        return Provider.BRAINTREE.value

    def _generate_id(self, length: int = 8) -> str:
        """Generate Braintree-style alphanumeric ID."""
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choices(chars, k=length))

    # Braintree processor response codes with realistic distribution
    FAILURE_CODES = [
        ("2000", 35),  # Do Not Honor
        ("2001", 25),  # Insufficient Funds
        ("2004", 15),  # Expired Card
        ("2010", 8),   # Card Issuer Declined CVV
        ("2005", 7),   # Invalid Account
        ("2046", 5),   # Declined
        ("2047", 3),   # Call Issuer
        ("2014", 2),   # Processor Declined
    ]

    FAILURE_MESSAGES = {
        "2000": "Do Not Honor - Contact card issuer.",
        "2001": "Insufficient Funds.",
        "2004": "Expired Card.",
        "2010": "Card Issuer Declined CVV.",
        "2005": "Invalid Card Number.",
        "2046": "Declined.",
        "2047": "Call Issuer. Possible Lost/Stolen Card.",
        "2014": "Processor Declined.",
    }

    def generate_payment(self) -> NormalizedPayment:
        """Generate a Braintree Transaction and normalize it."""
        braintree_txn = self._generate_braintree_transaction()
        return self._normalize(braintree_txn)

    def generate_failed_payment(self, failure_code: str | None = None) -> FailedPaymentEvent:
        """
        Generate a failed payment event from Braintree.

        Args:
            failure_code: Optional specific failure code (processor response code).
                         If None, randomly selected.

        Returns:
            FailedPaymentEvent with Braintree-specific failure details
        """
        payment = self.generate_payment()

        if failure_code is None:
            codes = []
            for code, weight in self.FAILURE_CODES:
                codes.extend([code] * weight)
            failure_code = random.choice(codes)

        normalized_failure = FailureCode.BRAINTREE_MAPPING.get(
            failure_code, FailureCode.CARD_DECLINED
        )

        original_charge_id = self._generate_id()

        return FailedPaymentEvent(
            payment=payment,
            failure_code=normalized_failure,
            failure_message=self.FAILURE_MESSAGES.get(
                failure_code, "Transaction declined."
            ),
            failure_timestamp=datetime.utcnow().isoformat() + "Z",
            original_charge_id=original_charge_id,
            retry_count=0,
        )

    def _generate_braintree_transaction(self) -> dict:
        """Generate raw Braintree Transaction object."""
        brand = random.choice(self.CARD_BRANDS)
        currency = random.choice(self.CURRENCIES)
        min_amt, max_amt = self.AMOUNT_RANGES.get(currency, (5.00, 1000.00))
        # Braintree uses decimal string amounts
        amount = round(random.uniform(min_amt, max_amt), 2)

        merchant = random.choice(self.MERCHANTS)

        first_name = random.choice(self.FIRST_NAMES)
        last_name = random.choice(self.LAST_NAMES)

        # Braintree statuses
        status = random.choices(
            ["submitted_for_settlement", "authorized", "settled", "failed", "gateway_rejected"],
            weights=[40, 25, 25, 7, 3]
        )[0]

        # Risk decision
        risk_decision = random.choices(
            ["Approve", "Review", "Decline"],
            weights=[85, 10, 5]
        )[0]

        return {
            # Braintree Transaction fields
            "id": self._generate_id(),
            "status": status,
            "type": "sale",
            "currencyIsoCode": currency,
            "amount": str(amount),  # Braintree uses string decimals
            "merchantAccountId": f"merchant_{self._generate_id(6)}",
            "subMerchantAccountId": None,
            "orderId": f"order_{self._generate_id(10)}",
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat(),

            # Customer information
            "customer": {
                "id": f"bt_cust_{self._generate_id(8)}",
                "firstName": first_name,
                "lastName": last_name,
                "company": random.choice([None, "Acme Corp", "TechStart Inc", "Global Solutions"]),
                "email": f"{first_name.lower()}.{last_name.lower()}@example.com",
                "phone": f"+1{random.randint(2000000000, 9999999999)}",
                "fax": None,
                "website": None,
            },

            # Credit card details
            "creditCard": {
                "token": f"token_{self._generate_id(12)}",
                "bin": str(random.randint(400000, 599999)),
                "last4": str(random.randint(1000, 9999)),
                "cardType": brand,
                "expirationMonth": str(random.randint(1, 12)).zfill(2),
                "expirationYear": str(random.randint(2025, 2030)),
                "customerLocation": random.choice(["US", "US", "US", "International"]),
                "cardholderName": f"{first_name} {last_name}",
                "uniqueNumberIdentifier": self._generate_id(32),
                "prepaid": random.choice(["No", "No", "No", "Yes"]),
                "healthcare": "Unknown",
                "debit": random.choice(["Yes", "No"]),
                "durbinRegulated": random.choice(["Yes", "No"]),
                "commercial": random.choice(["Yes", "No", "Unknown"]),
                "payroll": "Unknown",
                "issuingBank": random.choice(["Chase", "Bank of America", "Wells Fargo", "Citibank"]),
                "countryOfIssuance": "USA",
                "productId": random.choice(["A", "B", "C", "D", "E"]),
            },

            # Billing address
            "billing": {
                "id": self._generate_id(6),
                "firstName": first_name,
                "lastName": last_name,
                "company": None,
                "streetAddress": f"{random.randint(100, 9999)} {random.choice(['Broadway', 'Main St', 'Oak Ave', 'Park Blvd'])}",
                "extendedAddress": random.choice([None, None, f"Apt {random.randint(1, 500)}"]),
                "locality": random.choice(["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"]),
                "region": random.choice(["NY", "CA", "IL", "TX", "AZ"]),
                "postalCode": f"{random.randint(10000, 99999)}",
                "countryCodeAlpha2": "US",
                "countryCodeAlpha3": "USA",
                "countryCodeNumeric": "840",
                "countryName": "United States of America",
            },

            # Risk data
            "riskData": {
                "id": self._generate_id(6),
                "decision": risk_decision,
                "decisionReasons": [] if risk_decision == "Approve" else ["high_risk_email"] if risk_decision == "Review" else ["velocity_exceeded"],
                "deviceDataCaptured": True,
                "fraudServiceProvider": "kount",
                "transactionRiskScore": str(random.randint(0, 100)) if risk_decision != "Approve" else None,
            },

            # AVS/CVV responses
            "avsErrorResponseCode": None,
            "avsPostalCodeResponseCode": random.choice(["M", "M", "M", "N", "U"]),  # M=Match, N=No Match, U=Unknown
            "avsStreetAddressResponseCode": random.choice(["M", "M", "N", "U"]),
            "cvvResponseCode": random.choice(["M", "M", "M", "N", "U"]),

            # Processor response
            "processorResponseCode": "1000" if status != "failed" else random.choice(["2000", "2001", "2002"]),
            "processorResponseText": "Approved" if status != "failed" else random.choice(["Do Not Honor", "Insufficient Funds", "Card Expired"]),

            # Merchant data
            "merchant_data": {
                "name": merchant["name"],
                "mcc": merchant["mcc"],
                "category": merchant["category"],
            },

            # Additional fields
            "paymentInstrumentType": "credit_card",
            "planId": None,
            "subscriptionId": f"sub_{self._generate_id(8)}" if random.random() > 0.5 else None,
            "recurring": random.choice([True, False]),
        }

    def _normalize(self, braintree_txn: dict) -> NormalizedPayment:
        """Convert Braintree Transaction to normalized format."""
        credit_card = braintree_txn["creditCard"]
        customer = braintree_txn["customer"]
        billing = braintree_txn["billing"]
        merchant = braintree_txn["merchant_data"]
        risk = braintree_txn["riskData"]

        # Convert Braintree decimal string to cents
        amount_cents = int(Decimal(braintree_txn["amount"]) * 100)

        # Determine card funding type
        if credit_card.get("debit") == "Yes":
            card_funding = "debit"
        elif credit_card.get("prepaid") == "Yes":
            card_funding = "prepaid"
        else:
            card_funding = "credit"

        # Map Braintree risk decision to normalized risk level
        risk_level_map = {
            "Approve": "low",
            "Review": "medium",
            "Decline": "high",
        }

        return NormalizedPayment(
            # Provider identification
            provider=self.get_provider_name(),
            provider_payment_id=braintree_txn["id"],

            # Transaction details
            amount_cents=amount_cents,
            currency=braintree_txn["currencyIsoCode"],

            # Customer information
            customer_id=customer["id"],
            customer_email=customer["email"],
            customer_name=f"{customer['firstName']} {customer['lastName']}",

            # Card details
            card_brand=self._normalize_card_brand(credit_card["cardType"]),
            card_last4=credit_card["last4"],
            card_exp_month=int(credit_card["expirationMonth"]),
            card_exp_year=int(credit_card["expirationYear"]),
            card_funding=card_funding,

            # Merchant information
            merchant_name=merchant["name"],
            merchant_category=merchant["category"],
            merchant_mcc=merchant["mcc"],

            # Billing address
            billing_address={
                "line1": billing["streetAddress"],
                "line2": billing.get("extendedAddress"),
                "city": billing["locality"],
                "state": billing["region"],
                "postal_code": billing["postalCode"],
                "country": billing["countryCodeAlpha2"],
            },

            # Fraud signals (normalized)
            fraud_signals={
                "cvc_check": self._normalize_check_status(braintree_txn.get("cvvResponseCode")),
                "avs_check": self._normalize_check_status(braintree_txn.get("avsStreetAddressResponseCode")),
                "postal_check": self._normalize_check_status(braintree_txn.get("avsPostalCodeResponseCode")),
                "risk_level": risk_level_map.get(risk["decision"], "unknown"),
            },

            # Metadata
            metadata={
                "order_id": braintree_txn.get("orderId", ""),
                "subscription_id": braintree_txn.get("subscriptionId", ""),
                "recurring": braintree_txn.get("recurring", False),
                "processor_response_code": braintree_txn.get("processorResponseCode", ""),
                "processor_response_text": braintree_txn.get("processorResponseText", ""),
            },
            created_at=braintree_txn["createdAt"],

            # Raw data for debugging
            raw_provider_data=braintree_txn,
        )
