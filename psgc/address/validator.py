"""PSGC code validation."""

from __future__ import annotations

from psgc._loader import get_store


def validate(code: str) -> tuple[bool, str]:
    """Validate a PSGC code.

    Args:
        code: PSGC code string to validate.

    Returns:
        Tuple of (is_valid, reason).
    """
    return get_store().validate_code(code)


def is_valid(code: str) -> bool:
    """Check if a PSGC code is valid."""
    valid, _ = validate(code)
    return valid
