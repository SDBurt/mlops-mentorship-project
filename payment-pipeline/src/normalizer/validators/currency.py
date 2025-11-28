"""Currency validation using ISO 4217 codes."""

# Common ISO 4217 currency codes supported for payment processing
SUPPORTED_CURRENCIES = frozenset({
    # Major currencies
    "USD",  # US Dollar
    "EUR",  # Euro
    "GBP",  # British Pound
    "JPY",  # Japanese Yen
    "CAD",  # Canadian Dollar
    "AUD",  # Australian Dollar
    "CHF",  # Swiss Franc
    "CNY",  # Chinese Yuan
    # Additional supported currencies
    "HKD",  # Hong Kong Dollar
    "NZD",  # New Zealand Dollar
    "SEK",  # Swedish Krona
    "SGD",  # Singapore Dollar
    "NOK",  # Norwegian Krone
    "MXN",  # Mexican Peso
    "INR",  # Indian Rupee
    "BRL",  # Brazilian Real
    "KRW",  # South Korean Won
    "ZAR",  # South African Rand
    "DKK",  # Danish Krone
    "PLN",  # Polish Zloty
})


class CurrencyValidator:
    """Validates and normalizes currency codes."""

    def __init__(self, supported_currencies: frozenset[str] | None = None):
        """
        Initialize the currency validator.

        Args:
            supported_currencies: Set of supported currency codes.
                                  Defaults to SUPPORTED_CURRENCIES.
        """
        self.supported_currencies = supported_currencies or SUPPORTED_CURRENCIES

    def validate(self, currency: str | None) -> tuple[bool, str | None, str | None]:
        """
        Validate and normalize a currency code.

        Args:
            currency: Currency code to validate

        Returns:
            Tuple of (is_valid, normalized_currency, error_message)
        """
        if currency is None:
            return False, None, "Currency is required"

        # Normalize to uppercase
        normalized = currency.upper().strip()

        if not normalized:
            return False, None, "Currency cannot be empty"

        if len(normalized) != 3:
            return False, None, f"Currency must be 3 characters, got {len(normalized)}"

        if normalized not in self.supported_currencies:
            return False, None, f"Unsupported currency: {normalized}"

        return True, normalized, None

    def is_valid(self, currency: str | None) -> bool:
        """Check if a currency code is valid."""
        is_valid, _, _ = self.validate(currency)
        return is_valid

    def normalize(self, currency: str) -> str:
        """Normalize a currency code to uppercase."""
        return currency.upper().strip()
