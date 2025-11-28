"""Null normalization utilities."""

from typing import Any

# Values that should be treated as null
NULL_STRING_VALUES = {"", "null", "NULL", "Null", "none", "None", "NONE"}


def normalize_null(value: Any) -> Any | None:
    """
    Normalize various null representations to Python None.

    Handles:
    - None -> None
    - "" -> None
    - "null", "NULL", "Null" -> None
    - "none", "None", "NONE" -> None

    Args:
        value: Any value to check

    Returns:
        None if value represents null, otherwise the original value
    """
    if value is None:
        return None

    if isinstance(value, str) and value in NULL_STRING_VALUES:
        return None

    return value


def normalize_null_string(value: str | None) -> str | None:
    """
    Normalize null string values.

    Args:
        value: String value to normalize

    Returns:
        None if value represents null, otherwise the original string
    """
    if value is None:
        return None

    if value in NULL_STRING_VALUES:
        return None

    return value
