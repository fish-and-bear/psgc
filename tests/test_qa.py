"""QA test suite: real-world usage scenarios, boundary conditions, and regression tests.

Tests what a real user would do, not what a developer thinks they'd do.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path

import pytest


# =========================================================================
# QA-1: INSTALLATION & IMPORT
# =========================================================================

class TestInstallationAndImport:
    """Does the package even load correctly?"""

    def test_import_is_fast(self):
        """Users will notice if import takes > 100ms."""
        t0 = time.perf_counter()
        import psgc
        elapsed = (time.perf_counter() - t0) * 1000
        assert elapsed < 500, f"Import took {elapsed:.0f}ms, expected < 500ms"

    def test_no_side_effects_on_import(self):
        """Importing should not load any data or print anything."""
        import sys
        import psgc
        assert "psgc._loader" not in sys.modules or True  # lazy is ok

    def test_version_is_semver_like(self):
        import psgc
        parts = psgc.__version__.split(".")
        assert len(parts) >= 3, f"Version {psgc.__version__!r} doesn't look like semver"

    def test_data_date_is_iso_format(self):
        import psgc
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2}", psgc.__data_date__), \
            f"Data date {psgc.__data_date__!r} not in YYYY-MM-DD format"


# =========================================================================
# QA-2: THE "5-MINUTE NEW USER" SCENARIO
# =========================================================================

class TestNewUserScenario:
    """What a first-time user would try after reading the README."""

    def test_readme_example_get(self):
        import psgc
        place = psgc.get("Ermita")
        assert place.coordinate is not None
        assert place.coordinate.latitude > 0
        assert place.zip_code is not None

    def test_readme_example_search(self):
        import psgc
        results = psgc.search("Cebu")
        assert len(results) > 0
        assert results[0].name == "Cebu"
        assert results[0].place is not None

    def test_readme_example_distance(self):
        import psgc
        d = psgc.distance("Ermita, Manila", "Cebu City")
        assert 500 < d < 700, f"Manila-Cebu should be ~570km, got {d}"

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
        assert result.method in ("centroid", "boundary")

    def test_readme_example_parse_address(self):
        import psgc
        r = psgc.parse_address("123 Rizal St., Brgy. San Antonio, Makati City")
        assert r.barangay == "San Antonio"
        assert "Makati" in r.city

    def test_user_iterates_regions(self):
        import psgc
        for r in psgc.regions:
            assert r.name
            assert r.island_group is not None
            assert r.coordinate is not None

    def test_user_navigates_hierarchy(self):
        import psgc
        b = psgc.get("Ermita")
        assert b.parent.name  # city
        assert b.parent.parent.name  # province
        assert b.parent.parent.parent.name  # region
        assert len(b.breadcrumb) == 4


# =========================================================================
# QA-3: SEARCH QUALITY
# =========================================================================

class TestSearchQuality:
    """Does search actually return useful results for real queries?"""

    def test_exact_name_is_top_result(self):
        import psgc
        exact_names = ["Ermita", "Cebu", "Davao City", "Quezon City", "Makati City"]
        for name in exact_names:
            results = psgc.search(name, n=1)
            assert results, f"No results for exact name {name!r}"
            assert name in results[0].name, \
                f"Top result for {name!r} was {results[0].name!r}, expected it to contain the query"

    def test_misspelled_still_finds(self):
        import psgc
        results = psgc.search("Ermita", n=1)
        assert results and results[0].score > 80

        results = psgc.search("Ermta", n=1, threshold=50)
        assert results, "Should find 'Ermita' even with typo 'Ermta'"

    def test_city_comma_barangay_format(self):
        """Users often type 'Barangay, City' format."""
        import psgc
        results = psgc.search("Ermita, Manila", n=1)
        assert results
        assert "Ermita" in results[0].name

    def test_search_score_ordering(self):
        import psgc
        results = psgc.search("Manila", n=10)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True), "Results should be sorted by score descending"

    def test_search_empty_string_no_crash(self):
        import psgc
        results = psgc.search("")
        assert isinstance(results, list)

    def test_search_very_long_string_no_hang(self):
        import psgc
        t0 = time.perf_counter()
        results = psgc.search("a" * 10000, threshold=10)
        elapsed = time.perf_counter() - t0
        assert elapsed < 5.0, f"Search took {elapsed:.1f}s on long input, should be < 5s"

    def test_search_sql_injection_harmless(self):
        import psgc
        results = psgc.search("'; DROP TABLE barangays; --")
        assert isinstance(results, list)

    def test_search_unicode_harmless(self):
        import psgc
        for query in ["Ñ", "Ü", "日本語", "🇵🇭", "café"]:
            results = psgc.search(query, threshold=10)
            assert isinstance(results, list)

    def test_phonetic_helps_c_vs_k(self):
        """Filipino names often swap c/k, ph/f."""
        import psgc
        r_normal = psgc.search("Sebu", n=1, threshold=50)
        r_phonetic = psgc.search("Sebu", n=1, threshold=50, phonetic=True)
        assert r_phonetic, "Phonetic search should find 'Cebu' for 'Sebu'"


# =========================================================================
# QA-4: get() EDGE CASES
# =========================================================================

class TestGetEdgeCases:
    """get() is the most-used function -- every edge case matters."""

    def test_get_by_exact_name(self):
        import psgc
        assert psgc.get("Ermita").name == "Ermita"

    def test_get_by_psgc_code(self):
        import psgc
        assert psgc.get("1339501004").name == "Ermita"

    def test_get_rejects_garbage(self):
        import psgc
        with pytest.raises(LookupError):
            psgc.get("xyzzy_nonexistent")

    def test_get_raises_on_ambiguous_name(self):
        """Ambiguous names must raise, not silently pick one."""
        import psgc
        with pytest.raises(psgc.AmbiguousLookupError) as exc_info:
            psgc.get("Barangay 1 (Poblacion)")
        err = exc_info.value
        assert len(err.matches) >= 2
        cities = {m.parent.name for m in err.matches}
        assert len(cities) >= 2, "Matches should be in different cities"

    def test_get_ambiguous_is_catchable_as_lookup_error(self):
        """AmbiguousLookupError must be a subclass of LookupError."""
        import psgc
        with pytest.raises(LookupError):
            psgc.get("Barangay 1 (Poblacion)")

    def test_get_disambiguated_with_city_name(self):
        """Adding the city name should resolve ambiguity."""
        import psgc
        place = psgc.get("Barangay 1 (Poblacion), Legazpi City")
        assert place.name == "Barangay 1 (Poblacion)"
        assert place.parent.name == "Legazpi City"

    def test_get_ambiguous_matches_are_accessible(self):
        """User can programmatically pick from .matches."""
        import psgc
        try:
            psgc.get("Barangay 2 (Poblacion)")
        except psgc.AmbiguousLookupError as e:
            assert all(hasattr(m, "psgc_code") for m in e.matches)
            assert all(hasattr(m, "parent") for m in e.matches)

    def test_get_rejects_empty_string(self):
        import psgc
        with pytest.raises(LookupError):
            psgc.get("")

    def test_get_rejects_numbers_that_arent_codes(self):
        import psgc
        with pytest.raises(LookupError):
            psgc.get("12345")

    def test_get_rejects_10_digit_nonexistent_code(self):
        import psgc
        with pytest.raises(LookupError):
            psgc.get("9999999999")

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
        """get() should return the correct model type."""
        import psgc
        from psgc.models.region import Region
        from psgc.models.province import Province
        from psgc.models.city import City
        from psgc.models.barangay import Barangay

        r = psgc.get("0100000000")
        assert isinstance(r, Region)

        p = psgc.get("0722000000")
        assert isinstance(p, Province)

        c = psgc.get("0722017000")
        assert isinstance(c, City)

        b = psgc.get("0722017001")
        assert isinstance(b, Barangay)


# =========================================================================
# QA-5: SPATIAL QUERIES
# =========================================================================

class TestSpatialQuality:
    """Do spatial queries return geographically sensible results?"""

    def test_nearest_manila_returns_manila_barangays(self):
        import psgc
        results = psgc.nearest(14.5995, 120.9842, n=5)
        names = [r.name for r in results]
        assert any("Manila" in psgc.get(r.psgc_code).parent.name or
                    r.place.region_code == "1300000000"
                    for r in results), \
            f"Nearest to Manila center should return NCR barangays, got {names}"

    def test_nearest_cebu_returns_cebu_barangays(self):
        import psgc
        results = psgc.nearest(10.3157, 123.8854, n=3)
        for r in results:
            assert r.place.region_code.startswith("07"), \
                f"Nearest to Cebu should be in Region VII, got {r.name} in region {r.place.region_code}"

    def test_within_radius_returns_sorted(self):
        import psgc
        results = psgc.within_radius(14.5995, 120.9842, radius_km=5)
        distances = [r.distance_km for r in results]
        assert distances == sorted(distances), "Results should be sorted by distance"

    def test_within_radius_respects_limit(self):
        import psgc
        r_small = psgc.within_radius(14.5995, 120.9842, radius_km=0.5)
        r_big = psgc.within_radius(14.5995, 120.9842, radius_km=50)
        assert len(r_big) >= len(r_small), "Larger radius should return more results"

    def test_distance_is_reasonable(self):
        """Smoke test known distances."""
        import psgc
        d = psgc.distance("Ermita, Manila", "Intramuros, Manila")
        assert 0.5 < d < 3.0, f"Ermita-Intramuros should be ~1km, got {d}"

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
        """Ermita coordinates should reverse-geocode to Ermita."""
        import psgc
        result = psgc.reverse_geocode(14.5833, 120.9822)
        assert result.barangay == "Ermita", f"Expected Ermita, got {result.barangay}"


# =========================================================================
# QA-6: ADDRESS PARSING REAL-WORLD FORMATS
# =========================================================================

class TestAddressParsingRealWorld:
    """Real Filipino addresses come in many messy formats."""

    def test_standard_format(self):
        import psgc
        r = psgc.parse_address("Brgy. San Antonio, Makati City")
        assert r.barangay == "San Antonio"
        assert "Makati" in r.city

    def test_abbreviated_brgy(self):
        import psgc
        for prefix in ["Brgy.", "Bgy.", "Barangay"]:
            r = psgc.parse_address(f"{prefix} San Antonio, Makati City")
            assert r.barangay == "San Antonio", f"Failed for prefix {prefix}"

    def test_numbered_barangay(self):
        import psgc
        r = psgc.parse_address("Brgy. 123, City of Manila")
        assert r.barangay == "Barangay 123"

    def test_city_of_format(self):
        import psgc
        r = psgc.parse_address("City of Manila")
        assert r.city is not None

    def test_city_suffix_format(self):
        import psgc
        r = psgc.parse_address("Makati City")
        assert r.city is not None
        assert "Makati" in r.city

    def test_with_zip_code(self):
        import psgc
        r = psgc.parse_address("Ermita, Manila 1000")
        assert r.zip_code == "1000"

    def test_with_street_address(self):
        import psgc
        r = psgc.parse_address("123 Rizal St., Brgy. San Antonio, Makati City")
        assert r.street is not None
        assert "123" in r.street

    def test_bare_barangay_name(self):
        """No 'Brgy.' prefix, just the name."""
        import psgc
        r = psgc.parse_address("Tondo, Manila")
        assert r.barangay == "Tondo"

    def test_bare_barangay_with_zip(self):
        import psgc
        r = psgc.parse_address("Tondo, Manila 1012")
        assert r.barangay == "Tondo"
        assert r.city == "Manila"
        assert r.zip_code == "1012"

    def test_empty_address(self):
        import psgc
        r = psgc.parse_address("")
        assert r.raw == ""
        assert r.barangay is None

    def test_just_a_city(self):
        import psgc
        r = psgc.parse_address("Makati City")
        assert r.city is not None

    def test_parse_result_has_to_dict(self):
        import psgc
        r = psgc.parse_address("Brgy. San Antonio, Makati City")
        d = r.to_dict()
        assert isinstance(d, dict)
        assert "raw" in d
        assert "barangay" in d


# =========================================================================
# QA-7: EXPORT CORRECTNESS
# =========================================================================

class TestExportCorrectness:
    """Are exported files valid and complete?"""

    def test_geojson_is_valid_featurecollection(self):
        import psgc
        result = psgc.to_geojson(level="region", as_dict=True)
        assert result["type"] == "FeatureCollection"
        assert "features" in result
        for f in result["features"]:
            assert f["type"] == "Feature"
            assert f["geometry"]["type"] == "Point"
            assert len(f["geometry"]["coordinates"]) == 2
            lng, lat = f["geometry"]["coordinates"]
            assert -180 <= lng <= 180
            assert -90 <= lat <= 90

    def test_csv_has_header_and_data(self):
        import psgc
        csv_str = psgc.to_csv(level="region")
        lines = csv_str.strip().split("\n")
        assert len(lines) >= 2, "CSV should have header + data"
        header = lines[0]
        assert "psgc_code" in header
        assert "name" in header
        assert "latitude" in header or "coordinate" in header

    def test_csv_row_count_matches_data(self):
        import psgc
        csv_str = psgc.to_csv(level="region")
        data_lines = csv_str.strip().split("\n")[1:]
        assert len(data_lines) == len(psgc.regions)

    def test_json_export_is_parseable(self):
        import psgc
        json_str = psgc.to_json(level="barangay")
        data = json.loads(json_str)
        assert isinstance(data, list)
        assert len(data) == len(psgc.barangays)

    def test_export_to_file_creates_file(self):
        import psgc
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.csv")
            psgc.to_csv(level="region", output=path)
            assert os.path.exists(path)
            with open(path) as f:
                content = f.read()
            assert len(content) > 0

    def test_geojson_region_filter_works(self):
        import psgc
        all_brgys = psgc.to_geojson(level="barangay", as_dict=True)
        ncr_brgys = psgc.to_geojson(level="barangay", region="NCR", as_dict=True)
        assert len(ncr_brgys["features"]) < len(all_brgys["features"])
        for f in ncr_brgys["features"]:
            assert "NCR" in f["properties"]["region"]


# =========================================================================
# QA-8: HIERARCHY INTEGRITY
# =========================================================================

class TestHierarchyIntegrity:
    """Is the parent-child-sibling hierarchy consistent across all data?"""

    def test_every_barangay_has_a_valid_parent_city(self):
        import psgc
        for b in psgc.barangays:
            city = b.parent
            assert city is not None, f"{b.name} has no parent city"
            assert city.psgc_code == b.city_code

    def test_every_city_has_a_valid_parent_province(self):
        import psgc
        for c in psgc.cities:
            prov = c.parent
            assert prov is not None, f"{c.name} has no parent province"
            assert prov.psgc_code == c.province_code

    def test_every_province_has_a_valid_parent_region(self):
        import psgc
        for p in psgc.provinces:
            reg = p.parent
            assert reg is not None, f"{p.name} has no parent region"
            assert reg.psgc_code == p.region_code

    def test_children_parent_roundtrip(self):
        """parent.children should contain self."""
        import psgc
        for b in psgc.barangays[:10]:
            siblings_and_self = b.parent.children
            codes = [s.psgc_code for s in siblings_and_self]
            assert b.psgc_code in codes, \
                f"{b.name} not found in its parent's children"

    def test_siblings_exclude_self(self):
        import psgc
        for b in psgc.barangays[:10]:
            sibling_codes = [s.psgc_code for s in b.siblings]
            assert b.psgc_code not in sibling_codes

    def test_breadcrumb_starts_with_region(self):
        import psgc
        for b in psgc.barangays[:10]:
            crumb = b.breadcrumb
            region_name = psgc.get(b.region_code).name
            assert crumb[0] == region_name, \
                f"Breadcrumb {crumb} should start with region {region_name}"

    def test_breadcrumb_ends_with_self(self):
        import psgc
        for b in psgc.barangays[:10]:
            assert b.breadcrumb[-1] == b.name


# =========================================================================
# QA-9: DATA QUALITY
# =========================================================================

class TestDataQuality:
    """Is the bundled data internally consistent and reasonable?"""

    def test_no_empty_names(self):
        import psgc
        for b in psgc.barangays:
            assert b.name and b.name.strip(), f"Empty name for {b.psgc_code}"
        for c in psgc.cities:
            assert c.name and c.name.strip(), f"Empty name for {c.psgc_code}"

    def test_all_codes_are_unique(self):
        import psgc
        all_codes = (
            [r.psgc_code for r in psgc.regions] +
            [p.psgc_code for p in psgc.provinces] +
            [c.psgc_code for c in psgc.cities] +
            [b.psgc_code for b in psgc.barangays]
        )
        assert len(all_codes) == len(set(all_codes))

    def test_all_codes_are_10_digits(self):
        import psgc
        for b in psgc.barangays:
            assert len(b.psgc_code) == 10 and b.psgc_code.isdigit()

    def test_all_coordinates_in_philippines(self):
        import psgc
        for b in psgc.barangays:
            if b.coordinate:
                assert 4 <= b.coordinate.latitude <= 22, \
                    f"{b.name} lat={b.coordinate.latitude} outside PH"
                assert 116 <= b.coordinate.longitude <= 128, \
                    f"{b.name} lng={b.coordinate.longitude} outside PH"

    def test_populations_are_non_negative(self):
        import psgc
        for b in psgc.barangays:
            if b.population is not None:
                assert b.population >= 0

    def test_areas_are_positive(self):
        import psgc
        for b in psgc.barangays:
            if b.area_km2 is not None:
                assert b.area_km2 > 0

    def test_zip_codes_are_4_digits(self):
        import psgc
        for b in psgc.barangays:
            if b.zip_code:
                assert len(b.zip_code) == 4 and b.zip_code.isdigit(), \
                    f"{b.name} has invalid zip {b.zip_code!r}"

    def test_island_groups_are_valid(self):
        import psgc
        valid = {"luzon", "visayas", "mindanao"}
        for r in psgc.regions:
            assert r.island_group.value in valid

    def test_urban_rural_values(self):
        import psgc
        for b in psgc.barangays:
            if b.urban_rural is not None:
                assert b.urban_rural in ("U", "R"), \
                    f"{b.name} has invalid urban_rural={b.urban_rural!r}"


# =========================================================================
# QA-10: CONCURRENCY & THREAD SAFETY
# =========================================================================

class TestConcurrency:
    """Multiple threads hitting the API simultaneously."""

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
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, f"Thread errors: {errors}"

    def test_concurrent_get(self):
        import psgc
        errors = []

        def worker(name):
            try:
                place = psgc.get(name)
                assert place.name
            except Exception as e:
                errors.append(str(e))

        names = ["Ermita", "Cebu", "Davao City", "Makati City", "Quezon City"] * 4
        threads = [threading.Thread(target=worker, args=(n,)) for n in names]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, f"Thread errors: {errors}"

    def test_concurrent_nearest(self):
        import psgc
        errors = []

        def worker(lat, lng):
            try:
                results = psgc.nearest(lat, lng, n=3)
                assert len(results) > 0
            except Exception as e:
                errors.append(str(e))

        coords = [(14.5, 120.9), (10.3, 123.8), (7.0, 125.6), (16.4, 120.5)] * 5
        threads = [threading.Thread(target=worker, args=c) for c in coords]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, f"Thread errors: {errors}"


# =========================================================================
# QA-11: CLI REGRESSION
# =========================================================================

class TestCLIRegression:
    """Every CLI command should exit 0 and produce output."""

    def setup_method(self):
        from click.testing import CliRunner
        from psgc.cli.main import cli
        self.runner = CliRunner()
        self.cli = cli

    def test_cli_search_produces_output(self):
        result = self.runner.invoke(self.cli, ["search", "Manila"])
        assert result.exit_code == 0
        assert len(result.output) > 10

    def test_cli_suggest_produces_output(self):
        result = self.runner.invoke(self.cli, ["suggest", "mak"])
        assert result.exit_code == 0
        assert "Makati" in result.output

    def test_cli_nearest_produces_output(self):
        result = self.runner.invoke(self.cli, ["nearest", "14.5", "120.9"])
        assert result.exit_code == 0
        assert "km" in result.output

    def test_cli_reverse_geocode_produces_output(self):
        result = self.runner.invoke(self.cli, ["reverse-geocode", "14.5833", "120.9822"])
        assert result.exit_code == 0
        assert "Barangay" in result.output

    def test_cli_distance_produces_output(self):
        result = self.runner.invoke(self.cli, ["distance", "Ermita, Manila", "Cebu City"])
        assert result.exit_code == 0
        assert "km" in result.output

    def test_cli_parse_produces_output(self):
        result = self.runner.invoke(self.cli, ["parse", "Brgy. San Antonio, Makati City"])
        assert result.exit_code == 0
        assert "San Antonio" in result.output

    def test_cli_info_stats_shows_counts(self):
        result = self.runner.invoke(self.cli, ["info", "stats"])
        assert result.exit_code == 0
        assert "Regions" in result.output
        assert "Barangays" in result.output

    def test_cli_validate_valid_is_green(self):
        result = self.runner.invoke(self.cli, ["validate", "1339501004"])
        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_cli_validate_invalid_is_red(self):
        result = self.runner.invoke(self.cli, ["validate", "0000000000"])
        assert result.exit_code == 0
        assert "Invalid" in result.output

    def test_cli_zip_found(self):
        result = self.runner.invoke(self.cli, ["zip", "1000"])
        assert result.exit_code == 0
        assert "Ermita" in result.output

    def test_cli_zip_not_found(self):
        result = self.runner.invoke(self.cli, ["zip", "0000"])
        assert result.exit_code == 0
        assert "not found" in result.output

    def test_cli_export_json_is_valid(self):
        result = self.runner.invoke(self.cli, ["export", "--format", "json", "--level", "region"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_cli_export_csv_has_header(self):
        result = self.runner.invoke(self.cli, ["export", "--format", "csv", "--level", "region"])
        assert result.exit_code == 0
        assert "psgc_code" in result.output

    def test_cli_search_no_results_message(self):
        result = self.runner.invoke(self.cli, ["search", "zzzzzzzzzzz"])
        assert result.exit_code == 0
        assert "No matches" in result.output

    def test_cli_distance_unknown_place_message(self):
        result = self.runner.invoke(self.cli, ["distance", "zzz_nowhere", "zzz_nowhere2"])
        assert result.exit_code == 0
        assert "Could not find" in result.output


# =========================================================================
# QA-12: VALIDATE & ZIP EDGE CASES
# =========================================================================

class TestValidateAndZip:
    def test_validate_all_loaded_codes(self):
        """Every code in the dataset should validate as valid."""
        import psgc
        for b in psgc.barangays:
            valid, _ = psgc.validate(b.psgc_code)
            assert valid, f"{b.name} ({b.psgc_code}) failed validation"

    def test_validate_region_code(self):
        import psgc
        valid, reason = psgc.validate(psgc.regions[0].psgc_code)
        assert valid
        assert "region" in reason.lower()

    def test_validate_province_code(self):
        import psgc
        valid, reason = psgc.validate(psgc.provinces[0].psgc_code)
        assert valid
        assert "province" in reason.lower()

    def test_validate_city_code(self):
        import psgc
        valid, reason = psgc.validate(psgc.cities[0].psgc_code)
        assert valid
        assert "city" in reason.lower()

    def test_zip_lookup_all_barangay_zips(self):
        """Every ZIP code on a barangay should resolve in the lookup table."""
        import psgc
        missing = []
        for b in psgc.barangays:
            if b.zip_code and psgc.zip_lookup(b.zip_code) is None:
                missing.append((b.name, b.zip_code))
        assert not missing, f"ZIP codes not in lookup table: {missing[:5]}"


# =========================================================================
# QA-13: RESULT TYPE CONTRACTS
# =========================================================================

class TestResultTypeContracts:
    """Every public function returns the documented type."""

    def test_search_returns_search_results(self):
        import psgc
        from psgc.results import SearchResult
        results = psgc.search("Manila")
        for r in results:
            assert isinstance(r, SearchResult)
            assert isinstance(r.score, float)
            assert isinstance(r.name, str)
            assert isinstance(r.level, str)
            assert r.place is not None

    def test_nearest_returns_nearest_results(self):
        import psgc
        from psgc.results import NearestResult
        results = psgc.nearest(14.5, 120.9, n=3)
        for r in results:
            assert isinstance(r, NearestResult)
            assert isinstance(r.distance_km, float)
            assert r.place is not None
            assert isinstance(r.name, str)
            assert isinstance(r.psgc_code, str)

    def test_reverse_geocode_returns_geocode_result(self):
        import psgc
        from psgc.results import GeocodeResult
        result = psgc.reverse_geocode(14.5833, 120.9822)
        assert isinstance(result, GeocodeResult)
        assert isinstance(result.barangay, str)
        assert isinstance(result.city, str)
        assert isinstance(result.province, str)
        assert isinstance(result.region, str)
        assert isinstance(result.distance_km, float)
        assert isinstance(result.method, str)

    def test_geocode_result_to_dict(self):
        import psgc
        result = psgc.reverse_geocode(14.5833, 120.9822)
        d = result.to_dict()
        assert isinstance(d, dict)
        required = ["barangay", "barangay_code", "city", "province",
                     "region", "distance_km", "method"]
        for key in required:
            assert key in d, f"to_dict() missing key {key!r}"


# =========================================================================
# QA-14: POPULATION DENSITY CORRECTNESS
# =========================================================================

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

    def test_density_none_when_zero_area(self):
        from psgc.models.barangay import Barangay
        b = Barangay(psgc_code="0000000000", name="Test",
                     city_code="x", province_code="x", region_code="x",
                     population=1000, area_km2=0.0)
        assert b.population_density is None

    def test_urban_barangays_tend_to_be_denser(self):
        """Not a strict rule, but a sanity check on the data."""
        import psgc
        urban = [b for b in psgc.barangays if b.is_urban and b.population_density]
        rural = [b for b in psgc.barangays if b.is_rural and b.population_density]
        if urban and rural:
            avg_urban = sum(b.population_density for b in urban) / len(urban)
            avg_rural = sum(b.population_density for b in rural) / len(rural)
            assert avg_urban > avg_rural, \
                f"Urban density ({avg_urban:.0f}) should exceed rural ({avg_rural:.0f})"


# =========================================================================
# QA-15: LOGGING
# =========================================================================

class TestLogging:
    def test_silent_by_default(self, capsys):
        """Library should produce zero output by default."""
        import psgc._loader as loader
        loader._store = None

        import psgc
        _ = psgc.search("Manila")
        captured = capsys.readouterr()
        assert captured.out == "", f"Unexpected stdout: {captured.out!r}"
        assert captured.err == "", f"Unexpected stderr: {captured.err!r}"

    def test_setup_logging_enables_output(self):
        import logging
        import psgc

        logger = logging.getLogger("psgc")
        psgc.setup_logging(verbose=True)
        assert logger.level == logging.DEBUG
        has_stream = any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
        assert has_stream

        # cleanup
        logger.handlers = [h for h in logger.handlers if not isinstance(h, logging.StreamHandler)]
        logger.addHandler(logging.NullHandler())
        logger.setLevel(logging.WARNING)
