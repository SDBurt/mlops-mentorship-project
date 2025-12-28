"""Base validation classes and result types."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationError:
    """Represents a single validation error."""

    field: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for serialization."""
        return {
            "field": self.field,
            "code": self.code,
            "message": self.message,
        }


@dataclass
class ValidationResult:
    """Result of validating an event."""

    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    normalized_data: dict[str, Any] | None = None

    @property
    def error_codes(self) -> list[str]:
        """Get list of error codes."""
        return [e.code for e in self.errors]

    @property
    def primary_error_code(self) -> str | None:
        """Get the first error code, or None if valid."""
        return self.errors[0].code if self.errors else None

    def add_error(self, field: str, code: str, message: str) -> None:
        """Add a validation error."""
        self.errors.append(ValidationError(field=field, code=code, message=message))
        self.is_valid = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
        }
