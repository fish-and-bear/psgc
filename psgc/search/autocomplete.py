"""Prefix trie for fast autocomplete suggestions."""

from __future__ import annotations

from typing import Any


class _TrieNode:
    __slots__ = ("children", "entries")

    def __init__(self) -> None:
        self.children: dict[str, _TrieNode] = {}
        self.entries: list[dict[str, Any]] = []


class AutocompleteTrie:
    """Prefix trie built from geographic names for sub-millisecond lookups."""

    def __init__(self) -> None:
        self._root = _TrieNode()
        self._built = False

    def insert(self, name: str, metadata: dict[str, Any]) -> None:
        node = self._root
        for char in name.lower():
            if char not in node.children:
                node.children[char] = _TrieNode()
            node = node.children[char]
        node.entries.append({"name": name, **metadata})

    def suggest(self, prefix: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return up to `limit` suggestions matching the prefix."""
        node = self._root
        for char in prefix.lower():
            if char not in node.children:
                return []
            node = node.children[char]
        return self._collect(node, limit)

    def _collect(self, node: _TrieNode, limit: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        results.extend(node.entries[:limit])
        if len(results) >= limit:
            return results[:limit]
        for child in node.children.values():
            results.extend(self._collect(child, limit - len(results)))
            if len(results) >= limit:
                break
        return results[:limit]

    def build_from_store(self) -> None:
        """Populate trie from the data store."""
        if self._built:
            return
        from psgc._loader import get_store
        store = get_store()

        for r in store.regions:
            self.insert(r.name, {"psgc_code": r.psgc_code, "level": "region"})

        for p in store.provinces:
            self.insert(p.name, {"psgc_code": p.psgc_code, "level": "province"})

        for c in store.cities:
            self.insert(c.name, {"psgc_code": c.psgc_code, "level": "city"})

        for b in store.barangays:
            city_name = store.get_city(b.city_code).name
            self.insert(b.name, {"psgc_code": b.psgc_code, "level": "barangay", "city": city_name})
            full = f"{b.name}, {city_name}"
            self.insert(full, {"psgc_code": b.psgc_code, "level": "barangay", "city": city_name})

        self._built = True


_trie: AutocompleteTrie | None = None


def get_trie() -> AutocompleteTrie:
    """Get the singleton trie instance."""
    global _trie
    if _trie is None:
        _trie = AutocompleteTrie()
        _trie.build_from_store()
    return _trie


def suggest(prefix: str, limit: int = 10) -> list[dict[str, Any]]:
    """Return autocomplete suggestions for a prefix string."""
    if not prefix or not prefix.strip():
        return []
    return get_trie().suggest(prefix[:200], limit)
