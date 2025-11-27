# tests/test_providers.py
"""
Unit tests for payment providers.

Tests that each provider generates valid NormalizedPayment and FailedPaymentEvent
objects with correct field mappings and realistic data.
"""
import pytest
from temporal.providers import (
    generate_payment,
    generate_failed_payment,
    Provider,
    NormalizedPayment,
    FailedPaymentEvent,
    FailureCode,
)
from temporal.providers.stripe import StripeProvider
from temporal.providers.square import SquareProvider
from temporal.providers.braintree import BraintreeProvider


class TestNormalizedPayment:
    """Tests for the NormalizedPayment dataclass."""

    def test_to_dict_returns_all_fields(self):
        """to_dict should return a dictionary with all fields."""
        payment = NormalizedPayment(
            provider="stripe",
            provider_payment_id="pi_test123",
            amount_cents=5000,
            currency="USD",
            customer_id="cus_123",
            customer_email="test@example.com",
            customer_name="Test User",
            card_brand="visa",
            card_last4="4242",
            card_exp_month=12,
            card_exp_year=2025,
            card_funding="credit",
            merchant_name="Test Merchant",
            merchant_category="software",
            merchant_mcc="5734",
            billing_address={"city": "San Francisco"},
            fraud_signals={"cvc_check": "pass"},
            metadata={"order_id": "123"},
            created_at="2024-01-01T00:00:00Z",
            raw_provider_data={"id": "pi_test123"},
        )

        result = payment.to_dict()

        assert isinstance(result, dict)
        assert result["provider"] == "stripe"
        assert result["amount_cents"] == 5000
        assert result["card_brand"] == "visa"


class TestStripeProvider:
    """Tests for the Stripe payment provider."""

    @pytest.fixture
    def provider(self):
        return StripeProvider()

    def test_generates_normalized_payment(self, provider):
        """Should generate a valid NormalizedPayment."""
        payment = provider.generate_payment()

        assert isinstance(payment, NormalizedPayment)
        assert payment.provider == "stripe"

    def test_payment_has_required_fields(self, provider):
        """Payment should have all required fields populated."""
        payment = provider.generate_payment()

        assert payment.provider_payment_id.startswith("pi_")
        assert payment.amount_cents > 0
        assert payment.currency in ["USD", "EUR", "GBP", "CAD"]
        assert payment.customer_id.startswith("cus_")
        assert "@" in payment.customer_email
        assert len(payment.customer_name) > 0
        assert payment.card_brand in ["visa", "mastercard", "amex", "discover"]
        assert len(payment.card_last4) == 4
        assert 1 <= payment.card_exp_month <= 12
        assert payment.card_exp_year >= 2025

    def test_fraud_signals_normalized(self, provider):
        """Fraud signals should be in normalized format."""
        payment = provider.generate_payment()

        assert "cvc_check" in payment.fraud_signals
        assert "avs_check" in payment.fraud_signals
        assert "postal_check" in payment.fraud_signals
        assert payment.fraud_signals["cvc_check"] in ["pass", "fail", "unavailable", "unknown"]

    def test_raw_provider_data_preserved(self, provider):
        """Raw Stripe PaymentIntent should be preserved."""
        payment = provider.generate_payment()

        assert "raw_provider_data" in payment.to_dict()
        raw = payment.raw_provider_data
        assert raw["object"] == "payment_intent"
        assert "payment_method_details" in raw


class TestSquareProvider:
    """Tests for the Square payment provider."""

    @pytest.fixture
    def provider(self):
        return SquareProvider()

    def test_generates_normalized_payment(self, provider):
        """Should generate a valid NormalizedPayment."""
        payment = provider.generate_payment()

        assert isinstance(payment, NormalizedPayment)
        assert payment.provider == "square"

    def test_payment_has_required_fields(self, provider):
        """Payment should have all required fields populated."""
        payment = provider.generate_payment()

        assert len(payment.provider_payment_id) > 0
        assert payment.amount_cents > 0
        assert payment.currency in ["USD", "CAD", "GBP"]
        assert "@" in payment.customer_email
        assert payment.card_brand in ["visa", "mastercard", "amex", "discover", "unknown"]
        assert len(payment.card_last4) == 4

    def test_fraud_signals_normalized(self, provider):
        """Fraud signals should be in normalized format."""
        payment = provider.generate_payment()

        assert "cvc_check" in payment.fraud_signals
        assert "avs_check" in payment.fraud_signals
        assert payment.fraud_signals["cvc_check"] in ["pass", "fail", "unavailable", "unknown"]

    def test_raw_provider_data_preserved(self, provider):
        """Raw Square Payment should be preserved."""
        payment = provider.generate_payment()

        raw = payment.raw_provider_data
        assert "card_details" in raw
        assert "amount_money" in raw
        assert "source_type" in raw


class TestBraintreeProvider:
    """Tests for the Braintree payment provider."""

    @pytest.fixture
    def provider(self):
        return BraintreeProvider()

    def test_generates_normalized_payment(self, provider):
        """Should generate a valid NormalizedPayment."""
        payment = provider.generate_payment()

        assert isinstance(payment, NormalizedPayment)
        assert payment.provider == "braintree"

    def test_payment_has_required_fields(self, provider):
        """Payment should have all required fields populated."""
        payment = provider.generate_payment()

        assert len(payment.provider_payment_id) > 0
        assert payment.amount_cents > 0
        assert payment.currency in ["USD", "EUR", "GBP", "AUD"]
        assert payment.customer_id.startswith("bt_cust_")
        assert "@" in payment.customer_email
        assert payment.card_brand in ["visa", "mastercard", "amex", "discover", "unknown"]
        assert len(payment.card_last4) == 4

    def test_amount_converted_from_decimal(self, provider):
        """Amount should be converted from Braintree's decimal format to cents."""
        payment = provider.generate_payment()

        # Braintree uses decimal dollars, we convert to cents
        assert payment.amount_cents >= 500  # Min $5.00 = 500 cents
        assert payment.amount_cents <= 100000  # Max $1000.00 = 100000 cents

    def test_fraud_signals_include_risk_level(self, provider):
        """Braintree provides risk level from riskData."""
        payment = provider.generate_payment()

        assert "risk_level" in payment.fraud_signals
        assert payment.fraud_signals["risk_level"] in ["low", "medium", "high", "unknown"]

    def test_raw_provider_data_preserved(self, provider):
        """Raw Braintree Transaction should be preserved."""
        payment = provider.generate_payment()

        raw = payment.raw_provider_data
        assert "creditCard" in raw
        assert "customer" in raw
        assert "riskData" in raw


class TestGeneratePayment:
    """Tests for the generate_payment factory function."""

    def test_generates_from_specific_provider(self):
        """Should generate payment from specified provider."""
        stripe_payment = generate_payment(Provider.STRIPE)
        assert stripe_payment.provider == "stripe"

        square_payment = generate_payment(Provider.SQUARE)
        assert square_payment.provider == "square"

        braintree_payment = generate_payment(Provider.BRAINTREE)
        assert braintree_payment.provider == "braintree"

    def test_generates_random_provider(self):
        """Should generate payments from random providers."""
        providers_seen = set()

        # Generate enough payments to likely see all providers
        for _ in range(100):
            payment = generate_payment()
            providers_seen.add(payment.provider)

        # With weighted distribution, we should see all providers
        assert "stripe" in providers_seen
        assert "square" in providers_seen
        assert "braintree" in providers_seen

    def test_all_providers_return_normalized_payment(self):
        """All providers should return NormalizedPayment objects."""
        for provider in Provider:
            payment = generate_payment(provider)
            assert isinstance(payment, NormalizedPayment)
            assert payment.provider == provider.value


class TestCardBrandNormalization:
    """Tests for card brand normalization across providers."""

    def test_stripe_brands_normalized(self):
        """Stripe card brands should be normalized to lowercase."""
        provider = StripeProvider()
        # Generate multiple payments to test different brands
        brands = set()
        for _ in range(50):
            payment = provider.generate_payment()
            brands.add(payment.card_brand)

        # All brands should be lowercase
        for brand in brands:
            assert brand == brand.lower()
            assert brand in ["visa", "mastercard", "amex", "discover"]

    def test_square_brands_normalized(self):
        """Square card brands (uppercase) should be normalized to lowercase."""
        provider = SquareProvider()
        brands = set()
        for _ in range(50):
            payment = provider.generate_payment()
            brands.add(payment.card_brand)

        for brand in brands:
            assert brand == brand.lower()

    def test_braintree_brands_normalized(self):
        """Braintree card brands (mixed case) should be normalized to lowercase."""
        provider = BraintreeProvider()
        brands = set()
        for _ in range(50):
            payment = provider.generate_payment()
            brands.add(payment.card_brand)

        for brand in brands:
            assert brand == brand.lower()


class TestProviderWeightedSelection:
    """Tests for weighted random provider selection."""

    def test_weighted_distribution_approximate(self):
        """Random selection should roughly follow 60/25/15 distribution."""
        counts = {"stripe": 0, "square": 0, "braintree": 0}

        for _ in range(1000):
            payment = generate_payment()
            counts[payment.provider] += 1

        # Allow reasonable tolerance for statistical variation
        # Stripe: 60% = 600, allow 500-700
        # Square: 25% = 250, allow 150-350
        # Braintree: 15% = 150, allow 50-250
        assert 500 < counts["stripe"] < 700, f"Stripe count {counts['stripe']} not in expected range"
        assert 150 < counts["square"] < 350, f"Square count {counts['square']} not in expected range"
        assert 50 < counts["braintree"] < 250, f"Braintree count {counts['braintree']} not in expected range"


class TestNormalizedPaymentEdgeCases:
    """Edge case tests for NormalizedPayment."""

    def test_to_dict_handles_empty_fields(self):
        """to_dict should handle empty string and dict values correctly."""
        payment = NormalizedPayment(
            provider="stripe",
            provider_payment_id="pi_123",
            amount_cents=0,
            currency="USD",
            customer_id="",
            customer_email="",
            customer_name="",
            card_brand="visa",
            card_last4="4242",
            card_exp_month=12,
            card_exp_year=2025,
            card_funding="credit",
            merchant_name="",
            merchant_category="",
            merchant_mcc="",
            billing_address={},
            fraud_signals={},
            metadata={},
            created_at="",
            raw_provider_data={},
        )
        result = payment.to_dict()

        # Should include all fields, even empty ones
        assert result["amount_cents"] == 0
        assert result["customer_id"] == ""
        assert result["billing_address"] == {}
        assert result["fraud_signals"] == {}


class TestFailedPaymentEventGeneration:
    """Tests for failed payment event generation."""

    def test_stripe_generates_failed_event(self):
        """Stripe should generate valid FailedPaymentEvent."""
        provider = StripeProvider()
        event = provider.generate_failed_payment()

        assert isinstance(event, FailedPaymentEvent)
        assert isinstance(event.payment, NormalizedPayment)
        assert event.payment.provider == "stripe"
        assert event.failure_code in [
            FailureCode.CARD_DECLINED,
            FailureCode.INSUFFICIENT_FUNDS,
            FailureCode.EXPIRED_CARD,
            FailureCode.INCORRECT_CVC,
            FailureCode.PROCESSING_ERROR,
            FailureCode.FRAUD_SUSPECTED,
            FailureCode.INVALID_ACCOUNT,
        ]
        assert len(event.failure_message) > 0
        assert event.original_charge_id.startswith("ch_")
        assert event.retry_count == 0

    def test_square_generates_failed_event(self):
        """Square should generate valid FailedPaymentEvent."""
        provider = SquareProvider()
        event = provider.generate_failed_payment()

        assert isinstance(event, FailedPaymentEvent)
        assert event.payment.provider == "square"
        assert event.failure_code is not None
        assert event.retry_count == 0

    def test_braintree_generates_failed_event(self):
        """Braintree should generate valid FailedPaymentEvent."""
        provider = BraintreeProvider()
        event = provider.generate_failed_payment()

        assert isinstance(event, FailedPaymentEvent)
        assert event.payment.provider == "braintree"
        assert event.failure_code is not None
        assert event.retry_count == 0

    def test_specific_failure_code(self):
        """Should honor specific failure code request."""
        provider = StripeProvider()
        event = provider.generate_failed_payment("insufficient_funds")

        assert event.failure_code == FailureCode.INSUFFICIENT_FUNDS

    def test_to_dict_includes_all_fields(self):
        """FailedPaymentEvent.to_dict should include all fields."""
        provider = StripeProvider()
        event = provider.generate_failed_payment()
        result = event.to_dict()

        assert "payment" in result
        assert "failure_code" in result
        assert "failure_message" in result
        assert "failure_timestamp" in result
        assert "original_charge_id" in result
        assert "retry_count" in result


class TestGenerateFailedPayment:
    """Tests for the generate_failed_payment factory function."""

    def test_generates_from_specific_provider(self):
        """Should generate failed payment from specified provider."""
        stripe_event = generate_failed_payment(Provider.STRIPE)
        assert stripe_event.payment.provider == "stripe"

        square_event = generate_failed_payment(Provider.SQUARE)
        assert square_event.payment.provider == "square"

        braintree_event = generate_failed_payment(Provider.BRAINTREE)
        assert braintree_event.payment.provider == "braintree"

    def test_generates_random_provider(self):
        """Should generate failed payments from random providers."""
        providers_seen = set()

        for _ in range(100):
            event = generate_failed_payment()
            providers_seen.add(event.payment.provider)

        assert "stripe" in providers_seen
        assert "square" in providers_seen
        assert "braintree" in providers_seen

    def test_all_providers_return_failed_event(self):
        """All providers should return FailedPaymentEvent objects."""
        for provider in Provider:
            event = generate_failed_payment(provider)
            assert isinstance(event, FailedPaymentEvent)
            assert event.payment.provider == provider.value

    def test_failure_codes_have_realistic_distribution(self):
        """Failure codes should follow realistic distribution."""
        failure_codes = {}

        for _ in range(500):
            event = generate_failed_payment(Provider.STRIPE)
            code = event.failure_code
            failure_codes[code] = failure_codes.get(code, 0) + 1

        # card_declined and insufficient_funds should be most common
        assert failure_codes.get(FailureCode.CARD_DECLINED, 0) > 50
        assert failure_codes.get(FailureCode.INSUFFICIENT_FUNDS, 0) > 50


class TestFailureCodeMapping:
    """Tests for failure code mapping across providers."""

    def test_stripe_failure_codes_normalized(self):
        """Stripe failure codes should be normalized."""
        provider = StripeProvider()

        # Generate multiple events to see different failure codes
        codes_seen = set()
        for _ in range(100):
            event = provider.generate_failed_payment()
            codes_seen.add(event.failure_code)

        # All codes should be from the normalized set
        valid_codes = set(FailureCode.STRIPE_MAPPING.values())
        for code in codes_seen:
            assert code in valid_codes

    def test_square_failure_codes_normalized(self):
        """Square failure codes should be normalized."""
        provider = SquareProvider()

        codes_seen = set()
        for _ in range(100):
            event = provider.generate_failed_payment()
            codes_seen.add(event.failure_code)

        valid_codes = set(FailureCode.SQUARE_MAPPING.values())
        for code in codes_seen:
            assert code in valid_codes

    def test_braintree_failure_codes_normalized(self):
        """Braintree failure codes should be normalized."""
        provider = BraintreeProvider()

        codes_seen = set()
        for _ in range(100):
            event = provider.generate_failed_payment()
            codes_seen.add(event.failure_code)

        valid_codes = set(FailureCode.BRAINTREE_MAPPING.values())
        for code in codes_seen:
            assert code in valid_codes
