"""Edge case and regression tests for robustness."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


class TestCoordinateEdgeCases:
    def test_to_dict_roundtrip(self):
        from psgc.models.base import Coordinate
        c = Coordinate(latitude=14.5995, longitude=120.9842)
        d = c.to_dict()
        c2 = Coordinate(**d)
        assert c == c2

    def test_zero_coordinates(self):
        from psgc.models.base import Coordinate
        c = Coordinate(latitude=0.0, longitude=0.0)
        assert c.as_tuple() == (0.0, 0.0)

    def test_negative_coordinates(self):
        from psgc.models.base import Coordinate
        c = Coordinate(latitude=-6.0, longitude=-120.0)
        assert c.latitude == -6.0


class TestDataStoreEdgeCases:
    def test_get_region_not_found(self):
        from psgc._loader import get_store
        with pytest.raises(KeyError, match="Region not found"):
            get_store().get_region("9999999999")

    def test_get_province_not_found(self):
        from psgc._loader import get_store
        with pytest.raises(KeyError, match="Province not found"):
            get_store().get_province("9999999999")

    def test_get_city_not_found(self):
        from psgc._loader import get_store
        with pytest.raises(KeyError, match="City not found"):
            get_store().get_city("9999999999")

    def test_get_barangay_not_found(self):
        from psgc._loader import get_store
        with pytest.raises(KeyError, match="Barangay not found"):
            get_store().get_barangay("9999999999")

    def test_provinces_by_nonexistent_region(self):
        from psgc._loader import get_store
        assert get_store().provinces_by_region("9999999999") == []

    def test_cities_by_nonexistent_province(self):
        from psgc._loader import get_store
        assert get_store().cities_by_province("9999999999") == []

    def test_barangays_by_nonexistent_city(self):
        from psgc._loader import get_store
        assert get_store().barangays_by_city("9999999999") == []

    def test_neighbors_nonexistent(self):
        from psgc._loader import get_store
        assert get_store().get_neighbors("9999999999") == []

    def test_zip_not_found(self):
        from psgc._loader import get_store
        assert get_store().lookup_zip("0000") is None

    def test_validate_empty_string(self):
        from psgc._loader import get_store
        valid, reason = get_store().validate_code("")
        assert not valid

    def test_validate_letters(self):
        from psgc._loader import get_store
        valid, reason = get_store().validate_code("abcdefghij")
        assert not valid
        assert "numeric" in reason.lower()

    def test_validate_short(self):
        from psgc._loader import get_store
        valid, reason = get_store().validate_code("123")
        assert not valid
        assert "10 digits" in reason

    def test_flat_cache_returns_same_object(self):
        from psgc._loader import get_store
        store = get_store()
        f1 = store.build_flat()
        f2 = store.build_flat()
        assert f1 is f2

    def test_tree_cache_returns_same_object(self):
        from psgc._loader import get_store
        store = get_store()
        t1 = store.build_tree()
        t2 = store.build_tree()
        assert t1 is t2


class TestSearchEdgeCases:
    def test_empty_query(self):
        from psgc.search.fuzzy import search
        results = search("")
        assert isinstance(results, list)

    def test_special_characters(self):
        from psgc.search.fuzzy import search
        results = search("!@#$%^&*()", threshold=10.0)
        assert isinstance(results, list)

    def test_very_long_query(self):
        from psgc.search.fuzzy import search
        results = search("a" * 1000, threshold=10.0)
        assert isinstance(results, list)

    def test_unicode_query(self):
        from psgc.search.fuzzy import search
        results = search("Ni\u00f1a", threshold=30.0)
        assert isinstance(results, list)

    def test_search_n_zero(self):
        from psgc.search.fuzzy import search
        results = search("Manila", n=0)
        assert results == []

    def test_search_n_one(self):
        from psgc.search.fuzzy import search
        results = search("Manila", n=1)
        assert len(results) <= 1

    def test_search_returns_result_objects(self):
        from psgc.search.fuzzy import search
        from psgc.results import SearchResult
        results = search("Ermita", n=1)
        assert len(results) > 0
        r = results[0]
        assert isinstance(r, SearchResult)
        assert r.name
        assert r.score > 0
        assert r.psgc_code
        assert r.level
        assert r.place is not None

    def test_suggest_empty_prefix(self):
        from psgc.search.autocomplete import suggest
        results = suggest("")
        assert isinstance(results, list)
        assert len(results) == 0

    def test_suggest_single_char(self):
        from psgc.search.autocomplete import suggest
        results = suggest("a", limit=5)
        assert len(results) <= 5


class TestSpatialEdgeCases:
    def test_nearest_n_one(self):
        from psgc.geo.spatial import get_spatial_index
        results = get_spatial_index().nearest(14.5, 120.9, n=1)
        assert len(results) == 1

    def test_nearest_n_larger_than_data(self):
        from psgc.geo.spatial import get_spatial_index
        results = get_spatial_index().nearest(14.5, 120.9, n=10000)
        assert len(results) > 0

    def test_within_radius_zero(self):
        from psgc.geo.spatial import get_spatial_index
        results = get_spatial_index().within_radius(14.5, 120.9, radius_km=0.0)
        assert isinstance(results, list)

    def test_within_radius_very_large(self):
        from psgc.geo.spatial import get_spatial_index
        results = get_spatial_index().within_radius(14.5, 120.9, radius_km=2000)
        assert len(results) > 0

    def test_haversine_antipodal(self):
        from psgc.geo.distance import haversine
        dist = haversine(0, 0, 0, 180)
        assert abs(dist - 20015) < 100  # half circumference ~20,015 km

    def test_vincenty_same_point(self):
        from psgc.geo.distance import vincenty
        assert vincenty(14.5, 120.9, 14.5, 120.9) == 0.0

    def test_pip_empty_polygon(self):
        from psgc.geo.pip import point_in_polygon
        assert point_in_polygon(5, 5, []) is False

    def test_pip_two_points(self):
        from psgc.geo.pip import point_in_polygon
        assert point_in_polygon(5, 5, [(0, 0), (10, 10)]) is False

    def test_pip_concave_polygon(self):
        from psgc.geo.pip import point_in_polygon
        L_shape = [(0, 0), (10, 0), (10, 5), (5, 5), (5, 10), (0, 10)]
        assert point_in_polygon(2, 2, L_shape) is True
        assert point_in_polygon(7, 7, L_shape) is False
        assert point_in_polygon(7, 2, L_shape) is True


class TestAddressParserEdgeCases:
    def test_empty_string(self):
        from psgc.address.parser import parse_address
        result = parse_address("")
        assert result.raw == ""

    def test_just_zip(self):
        from psgc.address.parser import parse_address
        result = parse_address("1000")
        assert result.zip_code == "1000"

    def test_no_barangay_marker(self):
        from psgc.address.parser import parse_address
        result = parse_address("Makati City")
        assert result.city is not None

    def test_multiple_commas(self):
        from psgc.address.parser import parse_address
        result = parse_address("123 Street, Barangay 1, City, Province, Region")
        assert result.raw is not None

    def test_normalizer_empty(self):
        from psgc.address.normalizer import normalize_name
        assert normalize_name("") == ""

    def test_normalizer_whitespace_only(self):
        from psgc.address.normalizer import sanitize_input
        result = sanitize_input("   ")
        assert result == ""


class TestExportEdgeCases:
    def test_geojson_no_matching_region(self):
        from psgc.export.geojson import to_geojson
        result = to_geojson(level="barangay", region="NonexistentRegion", as_dict=True)
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 0

    def test_csv_empty_result(self):
        from psgc.export.formats import to_csv
        result = to_csv(level="barangay", region="NonexistentRegion")
        assert result == ""

    def test_json_empty_result(self):
        from psgc.export.formats import to_json
        result = to_json(level="barangay", region="NonexistentRegion")
        data = json.loads(result)
        assert data == []

    def test_csv_output_creates_dirs(self):
        from psgc.export.formats import to_csv
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sub" / "dir" / "test.csv"
            to_csv(level="region", output=str(path))
            assert path.exists()

    def test_geojson_province_level(self):
        from psgc.export.geojson import to_geojson
        result = to_geojson(level="province", as_dict=True)
        assert len(result["features"]) > 0
        for f in result["features"]:
            assert f["properties"]["level"] == "province"

    def test_geojson_city_level(self):
        from psgc.export.geojson import to_geojson
        result = to_geojson(level="city", as_dict=True)
        assert len(result["features"]) > 0


class TestModelSerialization:
    def test_barangay_to_dict(self):
        from psgc._loader import get_store
        b = get_store().barangays[0]
        d = b.to_dict()
        assert isinstance(d, dict)
        assert d["psgc_code"] == b.psgc_code
        assert d["name"] == b.name

    def test_city_to_dict(self):
        from psgc._loader import get_store
        c = get_store().cities[0]
        d = c.to_dict()
        assert "psgc_code" in d
        assert "province_code" in d

    def test_province_to_dict(self):
        from psgc._loader import get_store
        p = get_store().provinces[0]
        d = p.to_dict()
        assert "region_code" in d

    def test_region_to_dict(self):
        from psgc._loader import get_store
        r = get_store().regions[0]
        d = r.to_dict()
        assert "psgc_code" in d

    def test_flat_to_dict(self):
        from psgc._loader import get_store
        flat = get_store().build_flat()
        d = flat[0].to_dict()
        assert "level" in d
        assert isinstance(d["level"], str)

    def test_barangay_to_dict_has_coordinate(self):
        from psgc._loader import get_store
        b = get_store().barangays[0]
        d = b.to_dict()
        assert "coordinate" in d
        assert "latitude" in d["coordinate"]
        assert "longitude" in d["coordinate"]


class TestHierarchyIntegration:
    """Test full parent/child/sibling chains across levels."""

    def test_full_chain_up(self):
        from psgc._loader import get_store
        store = get_store()
        b = store.barangays[0]
        city = b.parent
        province = city.parent
        region = province.parent
        assert region.psgc_code == b.region_code

    def test_full_chain_down(self):
        from psgc._loader import get_store
        store = get_store()
        region = store.regions[0]
        if region.children:
            province = region.children[0]
            if province.children:
                city = province.children[0]
                if city.children:
                    brgy = city.children[0]
                    assert brgy.region_code == region.psgc_code

    def test_siblings_dont_include_self(self):
        from psgc._loader import get_store
        store = get_store()
        for b in store.barangays[:5]:
            siblings = b.siblings
            codes = [s.psgc_code for s in siblings]
            assert b.psgc_code not in codes

    def test_breadcrumb_consistency(self):
        from psgc._loader import get_store
        store = get_store()
        b = store.barangays[0]
        crumb = b.breadcrumb
        assert len(crumb) >= 3
        assert crumb[-1] == b.name

    def test_region_str(self):
        from psgc._loader import get_store
        r = get_store().regions[0]
        assert str(r) == r.name

    def test_barangay_repr(self):
        from psgc._loader import get_store
        b = get_store().barangays[0]
        r = repr(b)
        assert b.name in r
        assert b.psgc_code in r


class TestTopLevelAPI:
    """Test the public psgc.* API thoroughly."""

    def test_version(self):
        import psgc
        assert isinstance(psgc.__version__, str)
        assert "." in psgc.__version__

    def test_data_date(self):
        import psgc
        assert isinstance(psgc.__data_date__, str)
        assert "-" in psgc.__data_date__

    def test_regions_type(self):
        import psgc
        from psgc.models.region import Region
        assert isinstance(psgc.regions, list)
        assert isinstance(psgc.regions[0], Region)

    def test_search_callable(self):
        import psgc
        assert callable(psgc.search)
        results = psgc.search("Manila")
        assert isinstance(results, list)

    def test_suggest_callable(self):
        import psgc
        assert callable(psgc.suggest)
        results = psgc.suggest("man")
        assert isinstance(results, list)

    def test_distance_callable(self):
        import psgc
        assert callable(psgc.distance)
        d = psgc.distance("Ermita, Manila", "Intramuros, Manila")
        assert isinstance(d, float)
        assert d > 0

    def test_validate_callable(self):
        import psgc
        assert callable(psgc.validate)
        valid, reason = psgc.validate("1339501004")
        assert isinstance(valid, bool)
        assert isinstance(reason, str)

    def test_parse_address_callable(self):
        import psgc
        assert callable(psgc.parse_address)
        result = psgc.parse_address("Ermita, Manila")
        assert hasattr(result, "raw")

    def test_zip_lookup_callable(self):
        import psgc
        assert callable(psgc.zip_lookup)
        result = psgc.zip_lookup("1000")
        assert isinstance(result, dict)

    def test_nearest_callable(self):
        import psgc
        assert callable(psgc.nearest)
        results = psgc.nearest(14.5, 120.9, n=1)
        assert isinstance(results, list)

    def test_within_radius_callable(self):
        import psgc
        assert callable(psgc.within_radius)
        results = psgc.within_radius(14.5, 120.9, radius_km=1)
        assert isinstance(results, list)

    def test_reverse_geocode_callable(self):
        import psgc
        from psgc.results import GeocodeResult
        assert callable(psgc.reverse_geocode)
        result = psgc.reverse_geocode(14.5833, 120.9822)
        assert isinstance(result, GeocodeResult)

    def test_to_geojson_callable(self):
        import psgc
        assert callable(psgc.to_geojson)

    def test_to_csv_callable(self):
        import psgc
        assert callable(psgc.to_csv)

    def test_to_json_callable(self):
        import psgc
        assert callable(psgc.to_json)

    def test_to_yaml_callable(self):
        import psgc
        assert callable(psgc.to_yaml)

    def test_nonexistent_attr_raises(self):
        import psgc
        with pytest.raises(AttributeError, match="no attribute"):
            _ = psgc.this_does_not_exist

    def test_flat_is_list(self):
        import psgc
        assert isinstance(psgc.flat, list)
        assert len(psgc.flat) > 0

    def test_tree_is_list(self):
        import psgc
        assert isinstance(psgc.tree, list)
        assert len(psgc.tree) > 0


class TestDataIntegrity:
    """Verify the sample data is internally consistent."""

    def test_all_barangays_have_valid_city_code(self):
        from psgc._loader import get_store
        store = get_store()
        city_codes = {c.psgc_code for c in store.cities}
        for b in store.barangays:
            assert b.city_code in city_codes, f"Barangay {b.name} has invalid city_code {b.city_code}"

    def test_all_barangays_have_valid_province_code(self):
        from psgc._loader import get_store
        store = get_store()
        prov_codes = {p.psgc_code for p in store.provinces}
        for b in store.barangays:
            assert b.province_code in prov_codes, f"Barangay {b.name} has invalid province_code"

    def test_all_barangays_have_valid_region_code(self):
        from psgc._loader import get_store
        store = get_store()
        reg_codes = {r.psgc_code for r in store.regions}
        for b in store.barangays:
            assert b.region_code in reg_codes, f"Barangay {b.name} has invalid region_code"

    def test_all_cities_have_valid_province_code(self):
        from psgc._loader import get_store
        store = get_store()
        prov_codes = {p.psgc_code for p in store.provinces}
        for c in store.cities:
            assert c.province_code in prov_codes, f"City {c.name} has invalid province_code"

    def test_all_provinces_have_valid_region_code(self):
        from psgc._loader import get_store
        store = get_store()
        reg_codes = {r.psgc_code for r in store.regions}
        for p in store.provinces:
            assert p.region_code in reg_codes, f"Province {p.name} has invalid region_code"

    def test_all_psgc_codes_are_10_digits(self):
        from psgc._loader import get_store
        store = get_store()
        for r in store.regions:
            assert len(r.psgc_code) == 10 and r.psgc_code.isdigit(), f"Bad region code: {r.psgc_code}"
        for p in store.provinces:
            assert len(p.psgc_code) == 10 and p.psgc_code.isdigit(), f"Bad province code: {p.psgc_code}"
        for c in store.cities:
            assert len(c.psgc_code) == 10 and c.psgc_code.isdigit(), f"Bad city code: {c.psgc_code}"
        for b in store.barangays:
            assert len(b.psgc_code) == 10 and b.psgc_code.isdigit(), f"Bad barangay code: {b.psgc_code}"

    def test_all_coordinates_within_philippines(self):
        from psgc._loader import get_store
        store = get_store()
        for b in store.barangays:
            if b.coordinate:
                assert 4.0 <= b.coordinate.latitude <= 22.0, f"{b.name} lat out of PH range"
                assert 114.0 <= b.coordinate.longitude <= 128.0, f"{b.name} lon out of PH range"

    def test_no_duplicate_psgc_codes(self):
        from psgc._loader import get_store
        store = get_store()
        region_codes = {r.psgc_code for r in store.regions}
        all_codes: list[str] = []
        all_codes.extend(p.psgc_code for p in store.provinces if p.psgc_code not in region_codes)
        all_codes.extend(c.psgc_code for c in store.cities)
        all_codes.extend(b.psgc_code for b in store.barangays)
        assert len(all_codes) == len(set(all_codes)), "Duplicate PSGC codes found"

    def test_all_regions_have_island_group(self):
        from psgc._loader import get_store
        for r in get_store().regions:
            assert r.island_group is not None, f"Region {r.name} has no island_group"

    def test_all_barangays_have_coordinates(self):
        from psgc._loader import get_store
        for b in get_store().barangays:
            assert b.coordinate is not None, f"Barangay {b.name} missing coordinate"

    def test_population_non_negative(self):
        from psgc._loader import get_store
        store = get_store()
        for b in store.barangays:
            if b.population is not None:
                assert b.population >= 0

    def test_area_positive(self):
        from psgc._loader import get_store
        store = get_store()
        for b in store.barangays:
            if b.area_km2 is not None:
                assert b.area_km2 > 0
