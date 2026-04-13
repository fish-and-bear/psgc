"""Adjacency/neighbor queries for barangays."""

from __future__ import annotations

from psgc._loader import get_store
from psgc.models.barangay import Barangay


def get_neighbors(psgc_code: str) -> list[Barangay]:
    """Get adjacent barangays for a given PSGC code."""
    return get_store().get_neighbors(psgc_code)


def are_neighbors(code_a: str, code_b: str) -> bool:
    """Check if two barangays are adjacent."""
    neighbors = get_store().get_neighbors(code_a)
    return any(b.psgc_code == code_b for b in neighbors)
