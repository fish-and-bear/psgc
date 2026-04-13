"""Pre-built trigram index for fast fuzzy lookups."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _trigrams(text: str) -> set[str]:
    """Generate character trigrams from text."""
    text = f"  {text.lower()}  "
    return {text[i : i + 3] for i in range(len(text) - 2)}


class TrigramIndex:
    """Trigram-based index for approximate string matching.

    Provides fast candidate filtering before expensive
    edit-distance scoring.
    """

    def __init__(self) -> None:
        self._index: dict[str, set[int]] = defaultdict(set)
        self._entries: list[dict[str, Any]] = []

    def add(self, name: str, metadata: dict[str, Any]) -> None:
        idx = len(self._entries)
        self._entries.append({"name": name, **metadata})
        for trigram in _trigrams(name):
            self._index[trigram].add(idx)

    def candidates(self, query: str, max_results: int = 50) -> list[dict[str, Any]]:
        """Return candidate entries with the most trigram overlap."""
        query_tris = _trigrams(query)
        if not query_tris:
            return []

        scores: dict[int, int] = defaultdict(int)
        for tri in query_tris:
            for idx in self._index.get(tri, set()):
                scores[idx] += 1

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [self._entries[idx] for idx, _ in ranked[:max_results]]

    def build_from_store(self) -> None:
        from psgc._loader import get_store
        store = get_store()
        for r in store.regions:
            self.add(r.name, {"psgc_code": r.psgc_code, "level": "region"})
        for p in store.provinces:
            self.add(p.name, {"psgc_code": p.psgc_code, "level": "province"})
        for c in store.cities:
            self.add(c.name, {"psgc_code": c.psgc_code, "level": "city"})
        for b in store.barangays:
            self.add(b.name, {"psgc_code": b.psgc_code, "level": "barangay"})
