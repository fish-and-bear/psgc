"""Tests for fuzzy search and autocomplete."""

from __future__ import annotations


class TestFuzzySearch:
    def test_basic_search(self):
        from psgc.search.fuzzy import search
        results = search("Ermita")
        assert len(results) > 0
        assert results[0].name

    def test_search_with_city(self):
        from psgc.search.fuzzy import search
        results = search("Ermita, Manila")
        assert len(results) > 0
        found = any("Ermita" in r.name for r in results)
        assert found

    def test_search_threshold(self):
        from psgc.search.fuzzy import search
        high = search("Ermita", threshold=90.0)
        low = search("Ermita", threshold=50.0)
        assert len(low) >= len(high)

    def test_search_limit(self):
        from psgc.search.fuzzy import search
        results = search("Manila", n=2)
        assert len(results) <= 2

    def test_search_hooks(self):
        from psgc.search.fuzzy import search
        results = search("Cebu", match_hooks=["province"])
        assert len(results) > 0
        assert all(r.level == "province" for r in results)

    def test_search_returns_coordinates(self):
        from psgc.search.fuzzy import search
        results = search("Ermita", n=1)
        assert len(results) > 0
        assert results[0].coordinate is not None
        assert results[0].coordinate.latitude
        assert results[0].coordinate.longitude

    def test_search_phonetic(self):
        from psgc.search.fuzzy import search
        results = search("Sebu", phonetic=True, threshold=50.0)
        assert len(results) > 0

    def test_no_results(self):
        from psgc.search.fuzzy import search
        results = search("xyznonexistent12345", threshold=95.0)
        assert len(results) == 0


class TestAutocomplete:
    def test_suggest(self):
        from psgc.search.autocomplete import suggest
        results = suggest("mak")
        assert len(results) > 0
        assert all("name" in r for r in results)

    def test_suggest_limit(self):
        from psgc.search.autocomplete import suggest
        results = suggest("b", limit=3)
        assert len(results) <= 3

    def test_suggest_no_match(self):
        from psgc.search.autocomplete import suggest
        results = suggest("zzzzz")
        assert len(results) == 0

    def test_suggest_case_insensitive(self):
        from psgc.search.autocomplete import suggest
        upper = suggest("MAK")
        lower = suggest("mak")
        assert len(upper) == len(lower)


class TestTrigramIndex:
    def test_basic_index(self):
        from psgc.search.index import TrigramIndex
        idx = TrigramIndex()
        idx.add("Manila", {"code": "001"})
        idx.add("Makati", {"code": "002"})
        results = idx.candidates("Manila")
        assert len(results) > 0
        assert results[0]["name"] == "Manila"
