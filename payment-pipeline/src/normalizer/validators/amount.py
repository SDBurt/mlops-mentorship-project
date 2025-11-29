"""Amount validation for payment events."""

# Maximum amount in cents ($1,000,000 = 100,000,000 cents)
MAX_AMOUNT_CENTS = 100_000_000

# Minimum amount (typically 0, but some providers allow negative for refunds)
MIN_AMOUNT_CENTS = 0


class AmountValidator:
    """Validates payment amounts."""

    def __init__(
        self,
        min_amount: int = MIN_AMOUNT_CENTS,
        max_amount: int = MAX_AMOUNT_CENTS,
        allow_zero: bool = True,
    ):
        """
        Initialize the amount validator.

        Args:
            min_amount: Minimum allowed amount in cents
            max_amount: Maximum allowed amount in cents
            allow_zero: Whether to allow zero amounts
        """
        self.min_amount = min_amount
        self.max_amount = max_amount
        self.allow_zero = allow_zero

    def validate(self, amount: int | None) -> tuple[bool, int | None, str | None]:
        """
        Validate a payment amount.

        Args:
            amount: Amount in cents to validate

        Returns:
            Tuple of (is_valid, normalized_amount, error_message)
        """
        if amount is None:
            return False, None, "Amount is required"

        if not isinstance(amount, int):
            try:
                amount = int(amount)
            except (ValueError, TypeError):
                return False, None, f"Amount must be an integer, got {type(amount).__name__}"

        if amount < self.min_amount:
            return False, None, f"Amount must be >= {self.min_amount}, got {amount}"

        if amount > self.max_amount:
            return False, None, f"Amount must be <= {self.max_amount}, got {amount}"

        if not self.allow_zero and amount == 0:
            return False, None, "Amount cannot be zero"

        return True, amount, None

    def is_valid(self, amount: int | None) -> bool:
        """Check if an amount is valid."""
        is_valid, _, _ = self.validate(amount)
        return is_valid


class RefundAmountValidator(AmountValidator):
    """Validates refund amounts (allows zero for full refunds)."""

    def __init__(self, max_amount: int = MAX_AMOUNT_CENTS):
        super().__init__(min_amount=0, max_amount=max_amount, allow_zero=True)
