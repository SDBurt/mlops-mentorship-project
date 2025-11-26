# temporal/providers/base.py
"""
Base classes for payment provider abstraction.

Defines the common interface and normalized payment schema that all
provider implementations must follow.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class Provider(Enum):
    """Supported payment providers."""
    STRIPE = "stripe"
    SQUARE = "square"
    BRAINTREE = "braintree"


@dataclass
class NormalizedPayment:
    """
    Provider-agnostic payment schema for workflows.

    This normalized format allows workflows to process payments from any
    provider without provider-specific logic. The raw_provider_data field
    preserves the original format for debugging and audit purposes.
    """
    # Provider identification
    provider: str
    provider_payment_id: str

    # Transaction details
    amount_cents: int
    currency: str  # ISO 4217 (e.g., "USD", "EUR")

    # Customer information
    customer_id: str
    customer_email: str
    customer_name: str

    # Card details
    card_brand: str  # Normalized: "visa", "mastercard", "amex", "discover"
    card_last4: str
    card_exp_month: int
    card_exp_year: int
    card_funding: str  # "credit", "debit", "prepaid", "unknown"

    # Merchant information
    merchant_name: str
    merchant_category: str
    merchant_mcc: str  # Merchant Category Code

    # Billing address
    billing_address: dict = field(default_factory=dict)

    # Fraud signals (normalized)
    fraud_signals: dict = field(default_factory=lambda: {
        "cvc_check": "unknown",      # "pass", "fail", "unavailable", "unknown"
        "avs_check": "unknown",      # "pass", "fail", "unavailable", "unknown"
        "postal_check": "unknown",   # "pass", "fail", "unavailable", "unknown"
        "risk_level": "unknown",     # "low", "medium", "high", "unknown"
    })

    # Metadata
    metadata: dict = field(default_factory=dict)
    created_at: str = ""  # ISO 8601 timestamp

    # Original provider data (for debugging/audit)
    raw_provider_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for workflow input."""
        return asdict(self)


class PaymentProvider(ABC):
    """
    Abstract base class for payment provider implementations.

    Each provider must implement:
    - generate_payment(): Create synthetic payment data
    - get_provider_name(): Return the provider identifier
    """

    @abstractmethod
    def generate_payment(self) -> NormalizedPayment:
        """Generate a synthetic payment in normalized format."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider name (e.g., 'stripe', 'square')."""
        pass

    def _normalize_card_brand(self, brand: str) -> str:
        """Normalize card brand names across providers."""
        brand_lower = brand.lower()
        mappings = {
            # Stripe
            "visa": "visa",
            "mastercard": "mastercard",
            "amex": "amex",
            "american express": "amex",
            "discover": "discover",
            "diners": "diners",
            "jcb": "jcb",
            "unionpay": "unionpay",
            # Square uses uppercase
            "VISA": "visa",
            "MASTERCARD": "mastercard",
            "AMEX": "amex",
            "AMERICAN_EXPRESS": "amex",
            "DISCOVER": "discover",
            # Braintree uses mixed case
            "Visa": "visa",
            "MasterCard": "mastercard",
            "American Express": "amex",
            "Discover": "discover",
        }
        return mappings.get(brand, mappings.get(brand_lower, "unknown"))

    def _normalize_check_status(self, status: str | None) -> str:
        """Normalize verification check status across providers."""
        if status is None:
            return "unknown"
        status_lower = str(status).lower()
        if status_lower in ("pass", "passed", "cvv_accepted", "avs_accepted", "m", "y"):
            return "pass"
        elif status_lower in ("fail", "failed", "cvv_rejected", "avs_rejected", "n"):
            return "fail"
        elif status_lower in ("unavailable", "not_checked", "unchecked", "u", "s"):
            return "unavailable"
        return "unknown"
