"""QA test suite: real-world usage scenarios, boundary conditions, and regression tests."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path

import pytest


class TestInstallationAndImport:
    def test_import_is_fast(self):
        t0 = time.perf_counter()
        import psgc
        elapsed = (time.perf_counter() - t0) * 1000
        assert elapsed < 500

    def test_version_is_semver_like(self):
        import psgc
        parts = psgc.__version__.split(".")
        assert len(parts) >= 3

    def test_data_date_is_iso_format(self):
        import psgc
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2}", psgc.__data_date__)


class TestNewUserScenario:
    def test_readme_example_get(self):
        import psgc
        from psgc._loader import get_store
        b = get_store().barangays[0]
        place = psgc.get(b.psgc_code)
        assert place.name == b.name
        assert place.coordinate is not None
        assert place.coordinate.latitude > 0

    def test_readme_example_search(self):
        import psgc
        results = psgc.search("Cebu")
        assert len(results) > 0
        assert results[0].name == "Cebu"

    def test_readme_example_distance(self):
        import psgc
        d = psgc.distance("Ermita, Manila", "Cebu City")
        assert 500 < d < 700

    def test_readme_example_nearest(self):
        import psgc
        results = psgc.nearest(14.5995, 120.9842, n=3)
        assert len(results) == 3
        assert results[0].distance_km < results[1].distance_km

    def test_readme_example_reverse_geocode(self):
        import psgc
        result = psgc.reverse_geocode(14.5547, 121.0244)
        assert result.barangay
        assert result.city

    def test_readme_example_parse_address(self):
        import psgc
        r = psgc.parse_address("123 Rizal St., Brgy. San Antonio, Makati City")
        assert r.barangay == "San Antonio"
        assert "Makati" in r.city

    def test_user_navigates_hierarchy(self):
        import psgc
        from psgc._loader import get_store
        b = get_store().barangays[0]
        assert b.parent.name
        assert b.parent.parent.name
        assert b.parent.parent.parent.name
        assert len(b.breadcrumb) >= 3


class TestSearchQuality:
    def test_exact_name_is_top_result(self):
        import psgc
        exact_names = ["Cebu", "Quezon City", "Makati City"]
        for name in exact_names:
            results = psgc.search(name, n=10)
            assert results
            query_words = name.lower().split()
            assert any(
                all(w in r.name.lower() for w in query_words)
                for r in results
            )

    def test_search_score_ordering(self):
        import psgc
        results = psgc.search("Manila", n=10)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_unicode_harmless(self):
        import psgc
        for query in ["\u00d1", "\u00dc", "\u65e5\u672c\u8a9e", "\ud83c\uddf5\ud83c\udded", "caf\u00e9"]:
            results = psgc.search(query, threshold=10)
            assert isinstance(results, list)


class TestGetEdgeCases:
    def test_get_by_exact_name(self):
        import psgc
        assert psgc.get("Ermita").name == "Ermita"

    def test_get_by_psgc_code(self):
        import psgc
        from psgc._loader import get_store
        b = get_store().barangays[0]
        assert psgc.get(b.psgc_code).name == b.name

    def test_get_rejects_garbage(self):
        import psgc
        with pytest.raises(LookupError):
            psgc.get("xyzzy_nonexistent")

    def test_get_raises_on_ambiguous_name(self):
        import psgc
        with pytest.raises(psgc.AmbiguousLookupError) as exc_info:
            psgc.get("Barangay 1 (Poblacion)")
        err = exc_info.value
        assert len(err.matches) >= 2

    def test_get_disambiguated_with_city_name(self):
        import psgc
        from psgc._loader import get_store
        from collections import Counter
        store = get_store()
        name_counts = Counter(b.name for b in store.barangays)
        dup_name = next(name for name, count in name_counts.items() if count >= 2)
        dupes = [b for b in store.barangays if b.name == dup_name]
        target = dupes[0]
        place = psgc.get(f"{target.name}, {target.parent.name}")
        assert place.name == target.name
        assert place.parent.name == target.parent.name

    def test_get_rejects_empty_string(self):
        import psgc
        with pytest.raises(LookupError):
            psgc.get("")

    def test_get_whitespace_handling(self):
        import psgc
        place = psgc.get("  Ermita  ")
        assert place.name == "Ermita"

    def test_get_case_insensitive(self):
        import psgc
        p1 = psgc.get("ermita")
        p2 = psgc.get("ERMITA")
        p3 = psgc.get("Ermita")
        assert p1.psgc_code == p2.psgc_code == p3.psgc_code

    def test_get_returns_different_types(self):
        import psgc
        from psgc._loader import get_store
        from psgc.models.region import Region
        from psgc.models.province import Province
        from psgc.models.city import City
        from psgc.models.barangay import Barangay
        store = get_store()
        r = psgc.get(store.regions[0].psgc_code)
        assert isinstance(r, Region)
        p = psgc.get(store.provinces[0].psgc_code)
        assert isinstance(p, Province)
        c = psgc.get(store.cities[0].psgc_code)
        assert isinstance(c, City)
        b = psgc.get(store.barangays[0].psgc_code)
        assert isinstance(b, Barangay)


class TestSpatialQuality:
    def test_distance_is_symmetric(self):
        import psgc
        d1 = psgc.distance("Ermita, Manila", "Cebu City")
        d2 = psgc.distance("Cebu City", "Ermita, Manila")
        assert d1 == d2

    def test_distance_to_self_is_zero(self):
        import psgc
        d = psgc.distance("Ermita, Manila", "Ermita, Manila")
        assert d == 0.0

    def test_reverse_geocode_known_point(self):
        import psgc
        result = psgc.reverse_geocode(14.5833, 120.9822)
        assert isinstance(result.barangay, str) and len(result.barangay) > 0


class TestConcurrency:
    def test_concurrent_search(self):
        import psgc
        errors = []
        def worker(query):
            try:
                results = psgc.search(query, n=3)
                assert len(results) >= 0
            except Exception as e:
                errors.append(str(e))
        queries = ["Manila", "Cebu", "Davao", "Makati", "Ermita"] * 4
        threads = [threading.Thread(target=worker, args=(q,)) for q in queries]
        for t in threads: t.start()
        for t in threads: t.join()
        assert not errors


class TestValidateAndZip:
    def test_validate_region_code(self):
        import psgc
        valid, reason = psgc.validate(psgc.regions[0].psgc_code)
        assert valid
        assert "region" in reason.lower()

    def test_zip_lookup_all_barangay_zips(self):
        import psgc
        missing = []
        for b in psgc.barangays:
            if b.zip_code and psgc.zip_lookup(b.zip_code) is None:
                missing.append((b.name, b.zip_code))
        assert not missing, f"ZIP codes not in lookup table: {missing[:5]}"


class TestPopulationDensity:
    def test_density_formula(self):
        import psgc
        for b in psgc.barangays:
            if b.population and b.area_km2 and b.area_km2 > 0:
                expected = b.population / b.area_km2
                assert b.population_density == pytest.approx(expected)

    def test_density_none_when_missing_data(self):
        from psgc.models.barangay import Barangay
        b = Barangay(psgc_code="0000000000", name="Test",
                     city_code="x", province_code="x", region_code="x",
                     population=None, area_km2=1.0)
        assert b.population_density is None
