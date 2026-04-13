"""Tests targeting uncovered lines found by coverage analysis."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner


class TestCache:
    def test_cache_info_empty(self):
        from psgc.cache import cache_info
        info = cache_info()
        assert "path" in info
        assert "files" in info
        assert "size_bytes" in info

    def test_set_and_get_cached(self):
        from psgc.cache import clear_cache, get_cached, set_cached
        set_cached("test_key_123", {"hello": "world"})
        result = get_cached("test_key_123")
        assert result == {"hello": "world"}
        clear_cache()

    def test_get_cached_missing(self):
        from psgc.cache import get_cached
        assert get_cached("nonexistent_key_xyz_99999") is None

    def test_clear_cache(self):
        from psgc.cache import cache_info, clear_cache, set_cached
        set_cached("temp_key", [1, 2, 3])
        removed = clear_cache()
        assert removed >= 1
        info = cache_info()
        assert info["files"] == 0

    def test_cache_path_deterministic(self):
        from psgc.cache import cache_path
        p1 = cache_path("same_key")
        p2 = cache_path("same_key")
        assert p1 == p2

    def test_cache_path_different_keys(self):
        from psgc.cache import cache_path
        p1 = cache_path("key_a")
        p2 = cache_path("key_b")
        assert p1 != p2

    def test_cache_info_has_size_mb(self):
        from psgc.cache import cache_info, clear_cache, set_cached
        set_cached("size_test", {"data": "x" * 1000})
        info = cache_info()
        assert "size_mb" in info
        assert info["size_mb"] >= 0
        clear_cache()


class TestNeighborsModule:
    def test_get_neighbors_returns_list(self):
        from psgc.geo.neighbors import get_neighbors
        result = get_neighbors("1339501004")
        assert isinstance(result, list)

    def test_get_neighbors_nonexistent(self):
        from psgc.geo.neighbors import get_neighbors
        result = get_neighbors("9999999999")
        assert result == []

    def test_are_neighbors_false(self):
        from psgc.geo.neighbors import are_neighbors
        assert are_neighbors("1339501004", "9999999999") is False

    def test_are_neighbors_with_self(self):
        from psgc.geo.neighbors import are_neighbors
        assert are_neighbors("1339501004", "1339501004") is False


class TestLazyImport:
    def test_import_existing_module(self):
        from psgc._lazy import lazy_import
        result = lazy_import("json")
        assert hasattr(result, "dumps")

    def test_import_nonexistent_raises(self):
        from psgc._lazy import lazy_import
        with pytest.raises(ImportError, match="pip install"):
            lazy_import("scipy_nonexistent_module_xyz")

    def test_error_message_includes_extra(self):
        from psgc._lazy import lazy_import
        try:
            lazy_import("scipy.spatial")
        except ImportError as e:
            assert "geo" in str(e)


class TestCLIUncovered:
    def setup_method(self):
        self.runner = CliRunner()

    def test_nearest(self):
        from psgc.cli.main import cli
        result = self.runner.invoke(cli, ["nearest", "14.5995", "120.9842", "-n", "3"])
        assert result.exit_code == 0
        assert "km" in result.output

    def test_within_radius(self):
        from psgc.cli.main import cli
        result = self.runner.invoke(cli, ["within-radius", "14.5995", "120.9842", "--km", "2"])
        assert result.exit_code == 0
        assert "barangay" in result.output.lower()

    def test_reverse_geocode(self):
        from psgc.cli.main import cli
        result = self.runner.invoke(cli, ["reverse-geocode", "14.5833", "120.9822"])
        assert result.exit_code == 0
        assert "Barangay" in result.output

    def test_export_geojson(self):
        from psgc.cli.main import cli
        result = self.runner.invoke(cli, ["export", "--format", "geojson", "--level", "region"])
        assert result.exit_code == 0
        assert "FeatureCollection" in result.output

    def test_export_yaml(self):
        from psgc.cli.main import cli
        result = self.runner.invoke(cli, ["export", "--format", "yaml", "--level", "region"])
        assert result.exit_code == 0
        assert "psgc_code" in result.output

    def test_export_to_file(self):
        from psgc.cli.main import cli
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "out.json"
            result = self.runner.invoke(cli, ["export", "--format", "json", "--level", "region", "-o", str(path)])
            assert result.exit_code == 0
            assert "Exported" in result.output

    def test_search_no_results(self):
        from psgc.cli.main import cli
        result = self.runner.invoke(cli, ["search", "zzznonexistent999", "--threshold", "95"])
        assert result.exit_code == 0
        assert "No matches" in result.output

    def test_suggest_no_results(self):
        from psgc.cli.main import cli
        result = self.runner.invoke(cli, ["suggest", "zzzzzz"])
        assert result.exit_code == 0
        assert "No suggestions" in result.output

    def test_zip_not_found(self):
        from psgc.cli.main import cli
        result = self.runner.invoke(cli, ["zip", "0000"])
        assert result.exit_code == 0
        assert "not found" in result.output

    def test_search_with_hooks(self):
        from psgc.cli.main import cli
        result = self.runner.invoke(cli, ["search", "Cebu", "--hook", "province"])
        assert result.exit_code == 0
        assert "Cebu" in result.output

    def test_search_with_phonetic(self):
        from psgc.cli.main import cli
        result = self.runner.invoke(cli, ["search", "Sebu", "--phonetic"])
        assert result.exit_code == 0

    def test_distance_not_found(self):
        from psgc.cli.main import cli
        result = self.runner.invoke(cli, ["distance", "zzznonexistent", "zzz2"])
        assert result.exit_code == 0
        assert "Could not find" in result.output

    def test_export_with_region_filter(self):
        from psgc.cli.main import cli
        result = self.runner.invoke(cli, ["export", "--format", "csv", "--level", "barangay", "--region", "NCR"])
        assert result.exit_code == 0

    def test_export_with_island_group(self):
        from psgc.cli.main import cli
        result = self.runner.invoke(cli, ["export", "--format", "json", "--level", "region", "--island-group", "visayas"])
        assert result.exit_code == 0


class TestExportGaps:
    def test_geojson_province_filter(self):
        from psgc.export.geojson import to_geojson
        result = to_geojson(level="city", province="Cebu", as_dict=True)
        assert result["type"] == "FeatureCollection"
        for f in result["features"]:
            assert "Cebu" in f["properties"]["province"]

    def test_geojson_city_filter(self):
        from psgc.export.geojson import to_geojson
        result = to_geojson(level="barangay", city="Manila", as_dict=True)
        assert result["type"] == "FeatureCollection"
        for f in result["features"]:
            assert "Manila" in f["properties"]["city"]

    def test_csv_island_group_filter(self):
        from psgc.export.formats import to_csv
        result = to_csv(level="region", island_group="visayas")
        assert len(result) > 0
        assert "visayas" in result.lower() or "Visayas" in result

    def test_json_file_output(self):
        from psgc.export.formats import to_json
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            to_json(level="region", output=str(path))
            assert path.exists()
            data = json.loads(path.read_text())
            assert isinstance(data, list)

    def test_yaml_file_output(self):
        from psgc.export.formats import to_yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.yaml"
            to_yaml(level="region", output=str(path))
            assert path.exists()

    def test_geojson_file_output_with_filter(self):
        from psgc.export.geojson import to_geojson
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.geojson"
            to_geojson(level="barangay", region="NCR", output=str(path))
            assert path.exists()
            data = json.loads(path.read_text())
            assert data["type"] == "FeatureCollection"


class TestModelGaps:
    def test_extended_find_not_found(self):
        from psgc._loader import get_store
        trees = get_store().build_tree()
        result = trees[0].find("This Name Does Not Exist At All")
        assert result is None

    def test_extended_total_population(self):
        from psgc._loader import get_store
        trees = get_store().build_tree()
        for t in trees:
            pop = t.total_population
            assert isinstance(pop, int)
            assert pop >= 0

    def test_extended_is_leaf(self):
        from psgc._loader import get_store
        trees = get_store().build_tree()
        all_nodes = trees[0].flatten()
        leaves = [n for n in all_nodes if n.is_leaf]
        non_leaves = [n for n in all_nodes if not n.is_leaf]
        assert len(leaves) > 0
        assert len(non_leaves) > 0

    def test_flat_breadcrumb_region(self):
        from psgc.models.base import AdminLevel
        from psgc._loader import get_store
        flat = get_store().build_flat()
        region_items = [f for f in flat if f.level == AdminLevel.REGION]
        assert len(region_items) > 0
        for r in region_items:
            crumb = r.breadcrumb
            assert len(crumb) >= 1

    def test_flat_breadcrumb_barangay(self):
        from psgc.models.base import AdminLevel
        from psgc._loader import get_store
        flat = get_store().build_flat()
        brgy_items = [f for f in flat if f.level == AdminLevel.BARANGAY]
        assert len(brgy_items) > 0
        for b in brgy_items:
            crumb = b.breadcrumb
            assert len(crumb) == 4

    def test_flat_population_density(self):
        from psgc.models.base import AdminLevel
        from psgc._loader import get_store
        flat = get_store().build_flat()
        with_density = [f for f in flat if f.population_density is not None]
        assert len(with_density) > 0
        for f in with_density:
            assert f.population_density > 0

    def test_city_is_huc(self):
        from psgc._loader import get_store
        cities = get_store().cities
        hucs = [c for c in cities if c.is_huc]
        non_hucs = [c for c in cities if not c.is_huc]
        assert len(hucs) > 0
        assert len(non_hucs) > 0

    def test_province_str(self):
        from psgc._loader import get_store
        p = get_store().provinces[0]
        assert str(p) == p.name

    def test_city_str(self):
        from psgc._loader import get_store
        c = get_store().cities[0]
        assert str(c) == c.name

    def test_city_repr(self):
        from psgc._loader import get_store
        c = get_store().cities[0]
        r = repr(c)
        assert c.name in r
        assert c.psgc_code in r

    def test_province_repr(self):
        from psgc._loader import get_store
        p = get_store().provinces[0]
        r = repr(p)
        assert p.name in r

    def test_region_prefix(self):
        from psgc._loader import get_store
        for r in get_store().regions:
            assert len(r.region_prefix) == 2


class TestSearchIndexGaps:
    def test_trigram_index_build_from_store(self):
        from psgc.search.index import TrigramIndex
        idx = TrigramIndex()
        idx.build_from_store()
        results = idx.candidates("Manila")
        assert len(results) > 0

    def test_trigram_empty_query(self):
        from psgc.search.index import TrigramIndex
        idx = TrigramIndex()
        idx.add("test", {"code": "1"})
        results = idx.candidates("")
        assert isinstance(results, list)

    def test_trigram_no_match(self):
        from psgc.search.index import TrigramIndex
        idx = TrigramIndex()
        idx.add("hello", {"code": "1"})
        results = idx.candidates("zzzzz")
        assert len(results) == 0


class TestReverseGeocodeGaps:
    def test_reverse_without_boundaries(self):
        from psgc.geo.reverse import reverse_geocode
        result = reverse_geocode(14.5833, 120.9822, use_boundaries=False)
        assert result.method == "centroid"
        assert result.barangay

    def test_reverse_davao_area(self):
        from psgc.geo.reverse import reverse_geocode
        result = reverse_geocode(7.0707, 125.6087)
        assert result.barangay
        assert result.city

    def test_reverse_cebu_area(self):
        from psgc.geo.reverse import reverse_geocode
        result = reverse_geocode(10.3157, 123.8854)
        assert result.barangay

    def test_reverse_remote_location(self):
        from psgc.geo.reverse import reverse_geocode
        result = reverse_geocode(20.0, 122.0)
        assert result.barangay


class TestAddressParserGaps:
    def test_parse_with_province(self):
        from psgc.address.parser import parse_address
        result = parse_address("Brgy. Test, Some City, Some Province")
        assert result.province is not None

    def test_fuzzy_match_sets_region(self):
        from psgc.address.parser import parse_address
        result = parse_address("Brgy. Ermita, City of Manila")
        assert result.region is not None

    def test_invalid_zip_ignored(self):
        from psgc.address.parser import parse_address
        result = parse_address("Address 0001")
        assert result.zip_code is None

    def test_normalizer_expand_multiple(self):
        from psgc.address.normalizer import expand_abbreviations
        result = expand_abbreviations("Brgy. Test St. cor. Ave. Road")
        assert "barangay" in result
        assert "street" in result
        assert "corner" in result


class TestConfig:
    def test_config_data_dir(self):
        from psgc.config import config
        assert config.data_dir.exists()

    def test_config_core_data_dir(self):
        from psgc.config import config
        assert config.core_data_dir.exists()

    def test_config_verbose_default(self):
        from psgc.config import config
        assert isinstance(config.verbose, bool)

    def test_config_cache_dir(self):
        from psgc.config import config
        assert isinstance(config.cache_dir, Path)
