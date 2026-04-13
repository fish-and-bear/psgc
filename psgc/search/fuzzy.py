"""Fuzzy search engine using RapidFuzz with Filipino phonetic rules."""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from rapidfuzz import fuzz, process

from psgc._loader import get_store
from psgc.models.base import AdminLevel
from psgc.results import SearchResult

log = logging.getLogger(__name__)

MatchHook = Literal["barangay", "city", "province", "region"]

_PHONETIC_RULES: list[tuple[str, str]] = [
    ("ph", "f"),
    ("\u00f1", "ny"),
    ("ll", "ly"),
    ("gui", "gi"),
    ("gue", "ge"),
    ("qu", "k"),
    ("c(?=[eiy])", "s"),
    ("c", "k"),
    ("z", "s"),
    ("x", "ks"),
]

_COMPILED_RULES = [(re.compile(p, re.IGNORECASE), r) for p, r in _PHONETIC_RULES]


def _phonetic_normalize(text: str) -> str:
    result = text.lower().strip()
    for pattern, replacement in _COMPILED_RULES:
        result = pattern.sub(replacement, result)
    return result


def _sanitize(text: str, exclude: list[str] | None = None) -> str:
    result = text.lower().strip()
    if exclude:
        for word in exclude:
            result = result.replace(word.lower(), "")
    result = re.sub(r"\s+", " ", result).strip()
    return result


# Cached candidate lists (built once per store instance)
_cache_id: int | None = None
_cached_choices: list[tuple[str, str, str, Any, str]] = []
_cached_names: list[str] = []


def _ensure_cache() -> tuple[list[tuple[str, str, str, Any, str]], list[str]]:
    """Build and cache the candidate list on first call."""
    global _cache_id, _cached_choices, _cached_names

    store = get_store()
    store_id = id(store)

    if _cache_id == store_id and _cached_choices:
        return _cached_choices, _cached_names

    log.info("Building search index for %d barangays...", len(store.barangays))
    import time
    t0 = time.perf_counter()

    choices: list[tuple[str, str, str, Any, str]] = []

    for r in store.regions:
        n = _sanitize(r.name)
        choices.append((r.name, n, r.psgc_code, r, "region"))

    for p in store.provinces:
        n = _sanitize(p.name)
        choices.append((p.name, n, p.psgc_code, p, "province"))

    city_names: dict[str, str] = {}
    for c in store.cities:
        n = _sanitize(c.name)
        choices.append((c.name, n, c.psgc_code, c, "city"))
        city_names[c.psgc_code] = c.name

    for b in store.barangays:
        cn = city_names.get(b.city_code, "")
        if cn:
            full = f"{b.name}, {cn}"
            choices.append((full, _sanitize(full), b.psgc_code, b, "barangay"))
        choices.append((b.name, _sanitize(b.name), b.psgc_code, b, "barangay"))

    _cached_choices = choices
    _cached_names = [c[1] for c in choices]
    _cache_id = store_id

    elapsed = (time.perf_counter() - t0) * 1000
    log.info("Search index built: %d candidates in %.0fms", len(choices), elapsed)
    return _cached_choices, _cached_names


def search(
    query: str,
    n: int = 5,
    match_hooks: list[MatchHook] | None = None,
    threshold: float = 70.0,
    phonetic: bool = False,
) -> list[SearchResult]:
    """Search for geographic locations with fuzzy matching.

    Args:
        query: Search string (e.g. "Ermita, Manila")
        n: Maximum number of results to return
        match_hooks: Which levels to search (default: all)
        threshold: Minimum similarity score (0-100)
        phonetic: Apply Filipino phonetic normalization

    Returns:
        List of SearchResult objects. Each result has:
        - .place  -- the matched Region/Province/City/Barangay object
        - .score  -- similarity score (0-100)
        - .name   -- display name
        - .level  -- "region", "province", "city", or "barangay"
    """
    if match_hooks is None:
        match_hooks = ["barangay", "city", "province", "region"]

    if n <= 0:
        return []

    MAX_QUERY_LEN = 200
    if len(query) > MAX_QUERY_LEN:
        query = query[:MAX_QUERY_LEN]

    log.debug("Search query=%r, n=%d, hooks=%s, threshold=%.1f", query, n, match_hooks, threshold)

    normalize = _phonetic_normalize if phonetic else _sanitize
    query_clean = normalize(query)

    all_choices, all_names = _ensure_cache()

    if set(match_hooks) == {"barangay", "city", "province", "region"}:
        choices = all_choices
        names = all_names
    else:
        choices = [c for c in all_choices if c[4] in match_hooks]
        names = [c[1] for c in choices]

    if not choices:
        return []

    if phonetic:
        names = [_phonetic_normalize(c[1]) for c in choices]
        query_clean = _phonetic_normalize(query)

    matches = process.extract(query_clean, names, scorer=fuzz.WRatio, limit=n * 3, score_cutoff=threshold)

    seen_codes: set[str] = set()
    results: list[SearchResult] = []

    for match_name, score, idx in matches:
        if score < threshold:
            continue
        display, _, code, obj, level = choices[idx]
        if code in seen_codes:
            continue
        seen_codes.add(code)

        results.append(SearchResult(
            place=obj, score=round(score, 2), name=display, level=level,
        ))
        if len(results) >= n:
            break

    if results:
        log.debug("Search returned %d results, top=%s (%.1f)", len(results), results[0].name, results[0].score)
    else:
        log.debug("Search returned 0 results for %r", query)
    return results
