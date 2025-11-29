"""Custom exceptions for the payment gateway."""


class PaymentGatewayError(Exception):
    """Base exception for payment gateway errors."""

    pass


class SignatureVerificationError(PaymentGatewayError):
    """Raised when webhook signature verification fails."""

    def __init__(self, message: str = "Signature verification failed"):
        self.message = message
        super().__init__(self.message)


class SignatureExpiredError(SignatureVerificationError):
    """Raised when webhook signature timestamp is expired."""

    def __init__(self, message: str = "Signature timestamp expired"):
        super().__init__(message)


class PayloadValidationError(PaymentGatewayError):
    """Raised when webhook payload validation fails."""

    def __init__(self, message: str, errors: list[dict] | None = None):
        self.message = message
        self.errors = errors or []
        super().__init__(self.message)


class KafkaPublishError(PaymentGatewayError):
    """Raised when publishing to Kafka fails."""

    def __init__(self, message: str, topic: str | None = None):
        self.message = message
        self.topic = topic
        super().__init__(self.message)
