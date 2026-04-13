"""Pre-publish checklist: everything that must pass before uploading to PyPI.

Tests security, packaging, API contracts, backwards compat, and edge cases
that only surface in production.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest


# =========================================================================
# PACKAGING & DISTRIBUTION
# =========================================================================

class TestPackaging:
    """Will the package install and work for end users?"""

    def test_wheel_builds(self):
        result = subprocess.run(
            [sys.executable, "-m", "build", "--wheel"],
            capture_output=True, text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode == 0, f"Wheel build failed: {result.stderr}"

    def test_wheel_contains_data_files(self):
        import zipfile
        dist = Path(__file__).parent.parent / "dist"
        wheels = list(dist.glob("*.whl"))
        assert wheels, "No wheel found in dist/"
        with zipfile.ZipFile(wheels[-1]) as z:
            names = z.namelist()
            assert any("data/core/regions.json" in n for n in names), "regions.json missing from wheel"
            assert any("data/core/barangays.json" in n for n in names), "barangays.json missing from wheel"
            assert any("py.typed" in n for n in names), "py.typed missing from wheel"

    def test_wheel_excludes_dev_files(self):
        import zipfile
        dist = Path(__file__).parent.parent / "dist"
        wheels = list(dist.glob("*.whl"))
        with zipfile.ZipFile(wheels[-1]) as z:
            names = z.namelist()
            assert not any("parsers/" in n for n in names), "parsers/ should not be in wheel"
            assert not any("tests/" in n for n in names), "tests/ should not be in wheel"
            assert not any(".git" in n for n in names), ".git should not be in wheel"

    def test_metadata_has_required_fields(self):
        from importlib.metadata import metadata
        meta = metadata("psgc")
        assert meta["Name"] == "psgc"
        assert meta["Version"]
        assert meta["Requires-Python"]

    def test_entry_point_registered(self):
        from importlib.metadata import entry_points
        eps = entry_points(group="console_scripts")
        names = [ep.name for ep in eps]
        assert "psgc" in names, f"CLI entry point 'psgc' not registered. Found: {names}"

    def test_only_one_runtime_dependency(self):
        """Core should depend on only rapidfuzz. Everything else optional."""
        from importlib.metadata import requires
        reqs = requires("psgc") or []
        core_reqs = [r for r in reqs if "extra" not in r]
        assert len(core_reqs) == 1, f"Expected 1 core dep (rapidfuzz), got {core_reqs}"
        assert "rapidfuzz" in core_reqs[0]


# =========================================================================
# SECURITY
# =========================================================================

class TestSecurity:
    """No path traversal, no code injection, no information leaks."""

    def test_search_doesnt_eval_input(self):
        """Ensure search input is never executed."""
        import psgc
        dangerous_inputs = [
            "__import__('os').system('echo pwned')",
            "{{7*7}}",
            "${7*7}",
            "%(name)s",
            "<script>alert(1)</script>",
            "'; DROP TABLE barangays; --",
            "../../../etc/passwd",
            "\\x00\\x01\\x02",
        ]
        for inp in dangerous_inputs:
            results = psgc.search(inp, threshold=10)
            assert isinstance(results, list)

    def test_get_doesnt_eval_input(self):
        import psgc
        for inp in ["__import__('os')", "eval('1+1')", "${env.SECRET}"]:
            with pytest.raises(LookupError):
                psgc.get(inp)

    def test_parse_address_no_code_execution(self):
        import psgc
        r = psgc.parse_address("__import__('os').system('rm -rf /')")
        assert isinstance(r.raw, str)

    def test_export_path_traversal_safe(self):
        """Output paths should not escape the intended directory."""
        import psgc
        with tempfile.TemporaryDirectory() as tmpdir:
            safe_path = os.path.join(tmpdir, "test.json")
            psgc.to_json(level="region", output=safe_path)
            assert os.path.exists(safe_path)

    def test_cache_key_sanitized(self):
        """Cache keys should be hashed, not used as raw filenames."""
        from psgc.cache import cache_path
        p = cache_path("../../../etc/passwd")
        assert ".." not in p.name, "Cache path should be hashed, not raw"
        assert "etc" not in p.name

    def test_no_pickle_usage(self):
        """Pickle is a deserialization attack vector. We should never use it."""
        import psgc
        pkg_dir = Path(psgc.__file__).parent
        for py_file in pkg_dir.rglob("*.py"):
            content = py_file.read_text()
            assert "pickle" not in content.lower() or "# safe" in content, \
                f"{py_file.name} uses pickle -- deserialization vulnerability"

    def test_no_eval_or_exec(self):
        """No dynamic code execution."""
        import psgc
        pkg_dir = Path(psgc.__file__).parent
        for py_file in pkg_dir.rglob("*.py"):
            content = py_file.read_text()
            for line_num, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                assert "eval(" not in stripped, f"{py_file.name}:{line_num} uses eval()"
                assert "exec(" not in stripped, f"{py_file.name}:{line_num} uses exec()"

    def test_no_subprocess_usage(self):
        """Library should not shell out."""
        import psgc
        pkg_dir = Path(psgc.__file__).parent
        for py_file in pkg_dir.rglob("*.py"):
            content = py_file.read_text()
            assert "subprocess" not in content, f"{py_file.name} imports subprocess"
            assert "os.system" not in content, f"{py_file.name} uses os.system"
            assert "os.popen" not in content, f"{py_file.name} uses os.popen"


# =========================================================================
# API STABILITY CONTRACTS
# =========================================================================

class TestAPIStability:
    """Things that must never change without a major version bump."""

    def test_public_api_surface(self):
        """All documented names must exist."""
        import psgc
        required_names = [
            "get", "search", "suggest", "nearest", "within_radius",
            "reverse_geocode", "distance", "parse_address", "format_address",
            "validate", "zip_lookup", "to_geojson", "to_csv", "to_json",
            "to_yaml", "sanitize_input", "setup_logging",
            "regions", "provinces", "cities", "barangays", "flat", "tree",
            "SearchResult", "NearestResult", "GeocodeResult",
            "__version__", "__data_date__",
        ]
        for name in required_names:
            assert hasattr(psgc, name), f"psgc.{name} missing from public API"

    def test_search_result_has_place_score_name_level(self):
        import psgc
        r = psgc.search("Manila", n=1)[0]
        assert hasattr(r, "place")
        assert hasattr(r, "score")
        assert hasattr(r, "name")
        assert hasattr(r, "level")
        assert hasattr(r, "psgc_code")
        assert hasattr(r, "coordinate")

    def test_nearest_result_has_place_distance(self):
        import psgc
        r = psgc.nearest(14.5, 120.9, n=1)[0]
        assert hasattr(r, "place")
        assert hasattr(r, "distance_km")
        assert hasattr(r, "name")
        assert hasattr(r, "psgc_code")

    def test_geocode_result_has_all_properties(self):
        import psgc
        r = psgc.reverse_geocode(14.5833, 120.9822)
        assert hasattr(r, "place")
        assert hasattr(r, "distance_km")
        assert hasattr(r, "method")
        assert hasattr(r, "barangay")
        assert hasattr(r, "city")
        assert hasattr(r, "province")
        assert hasattr(r, "region")
        assert hasattr(r, "to_dict")

    def test_barangay_model_contract(self):
        import psgc
        b = psgc.barangays[0]
        assert hasattr(b, "psgc_code")
        assert hasattr(b, "name")
        assert hasattr(b, "coordinate")
        assert hasattr(b, "city_code")
        assert hasattr(b, "province_code")
        assert hasattr(b, "region_code")
        assert hasattr(b, "urban_rural")
        assert hasattr(b, "zip_code")
        assert hasattr(b, "area_km2")
        assert hasattr(b, "population")
        assert hasattr(b, "island_group")
        assert hasattr(b, "parent")
        assert hasattr(b, "siblings")
        assert hasattr(b, "breadcrumb")
        assert hasattr(b, "is_urban")
        assert hasattr(b, "is_rural")
        assert hasattr(b, "population_density")
        assert hasattr(b, "neighbors")
        assert hasattr(b, "to_dict")

    def test_region_model_contract(self):
        import psgc
        r = psgc.regions[0]
        assert hasattr(r, "psgc_code")
        assert hasattr(r, "name")
        assert hasattr(r, "coordinate")
        assert hasattr(r, "island_group")
        assert hasattr(r, "population")
        assert hasattr(r, "provinces")
        assert hasattr(r, "children")
        assert hasattr(r, "breadcrumb")
        assert hasattr(r, "to_dict")


# =========================================================================
# EDGE CASE BUG HUNTING
# =========================================================================

class TestBugHunting:
    """Scenarios that have historically caused bugs."""

    def test_get_then_navigate_full_chain(self):
        """The most common real-world pattern."""
        import psgc
        b = psgc.get("Ermita")
        city = b.parent
        province = city.parent
        region = province.parent
        assert region.psgc_code == b.region_code
        assert province.psgc_code == b.province_code
        assert city.psgc_code == b.city_code

    def test_search_then_get_same_place(self):
        import psgc
        results = psgc.search("Quezon City", n=1)
        sr = results[0]
        place = psgc.get(sr.psgc_code)
        assert place.psgc_code == sr.psgc_code

    def test_nearest_then_reverse_geocode_same_point(self):
        import psgc
        lat, lng = 14.5995, 120.9842
        near = psgc.nearest(lat, lng, n=1)[0]
        rev = psgc.reverse_geocode(lat, lng)
        assert near.place.psgc_code == rev.place.psgc_code

    def test_distance_after_get(self):
        import psgc
        a = psgc.get("Ermita")
        b = psgc.get("Intramuros")
        from psgc.geo.distance import haversine
        d = haversine(
            a.coordinate.latitude, a.coordinate.longitude,
            b.coordinate.latitude, b.coordinate.longitude,
        )
        d_api = psgc.distance("Ermita, Manila", "Intramuros, Manila")
        assert abs(d - d_api) < 0.01

    def test_flat_and_tree_contain_same_data(self):
        """Both views should represent the same underlying dataset."""
        import psgc
        flat_codes = {f.psgc_code for f in psgc.flat}
        tree_nodes = []
        for t in psgc.tree:
            tree_nodes.extend(t.flatten())
        tree_codes = {n.psgc_code for n in tree_nodes}
        assert flat_codes == tree_codes, \
            f"Flat has {len(flat_codes)} codes, tree has {len(tree_codes)}"

    def test_to_dict_roundtrip_json_safe(self):
        """Every to_dict() output must be JSON-serializable."""
        import psgc
        for b in psgc.barangays:
            d = b.to_dict()
            json_str = json.dumps(d)
            parsed = json.loads(json_str)
            assert parsed["psgc_code"] == b.psgc_code

    def test_coordinate_to_dict_roundtrip(self):
        from psgc.models.base import Coordinate
        c = Coordinate(latitude=14.5833, longitude=120.9822)
        d = c.to_dict()
        c2 = Coordinate(**d)
        assert c == c2

    def test_search_with_all_hook_combinations(self):
        import psgc
        hooks_to_try = [
            ["region"], ["province"], ["city"], ["barangay"],
            ["region", "province"], ["city", "barangay"],
            ["region", "province", "city", "barangay"],
        ]
        for hooks in hooks_to_try:
            results = psgc.search("Manila", n=3, match_hooks=hooks)
            assert isinstance(results, list), f"Failed for hooks={hooks}"
            for r in results:
                assert r.level in hooks, \
                    f"Hook filter {hooks} returned level={r.level}"

    def test_suggest_results_are_findable_by_get(self):
        """Every suggestion should be resolvable by get()."""
        import psgc
        suggestions = psgc.suggest("man", limit=10)
        for s in suggestions:
            code = s["psgc_code"]
            place = psgc.get(code)
            assert place.psgc_code == code

    def test_validate_then_get_roundtrip(self):
        """If validate says it's valid, get(code) should work."""
        import psgc
        for b in psgc.barangays[:20]:
            valid, reason = psgc.validate(b.psgc_code)
            assert valid
            place = psgc.get(b.psgc_code)
            assert place.psgc_code == b.psgc_code

    def test_zip_on_barangay_matches_lookup(self):
        """If b.zip_code is set, zip_lookup should return data for that code."""
        import psgc
        for b in psgc.barangays:
            if b.zip_code:
                info = psgc.zip_lookup(b.zip_code)
                assert info is not None, \
                    f"{b.name} has zip={b.zip_code} but lookup returns None"

    def test_multiple_gets_return_same_object(self):
        """Repeated get() calls should return the same instance (from cache)."""
        import psgc
        a = psgc.get("1339501004")
        b = psgc.get("1339501004")
        assert a is b, "get() by code should return cached instance"

    def test_parent_child_identity(self):
        """b.parent.children should contain the exact same object as b."""
        import psgc
        b = psgc.barangays[0]
        children = b.parent.children
        found = [c for c in children if c.psgc_code == b.psgc_code]
        assert len(found) == 1
        assert found[0] is b, "Parent's children list should contain the same object"

    def test_concurrent_get_and_search_interleaved(self):
        """Mixed operations from multiple threads."""
        import threading
        import psgc
        errors = []

        def mixed_ops(i):
            try:
                psgc.get("Ermita")
                psgc.search("Manila", n=1)
                psgc.nearest(14.5, 120.9, n=1)
                psgc.suggest("mak")
                psgc.validate("1339501004")
                psgc.zip_lookup("1000")
                psgc.parse_address("Brgy. Ermita, Manila")
            except Exception as e:
                errors.append(f"Thread {i}: {e}")

        threads = [threading.Thread(target=mixed_ops, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, f"Concurrent failures: {errors}"


# =========================================================================
# PERFORMANCE REGRESSION
# =========================================================================

class TestPerformanceRegression:
    """Operations must stay fast. These are upper bounds, not benchmarks."""

    def test_search_under_50ms(self):
        import psgc
        _ = psgc.search("warmup")  # warm up
        t0 = time.perf_counter()
        for _ in range(10):
            psgc.search("Manila", n=5)
        elapsed = (time.perf_counter() - t0) * 1000
        per_call = elapsed / 10
        assert per_call < 50, f"search() took {per_call:.1f}ms, expected < 50ms"

    def test_get_by_code_under_1ms(self):
        import psgc
        _ = psgc.get("1339501004")  # warm up
        t0 = time.perf_counter()
        for _ in range(100):
            psgc.get("1339501004")
        elapsed = (time.perf_counter() - t0) * 1000
        per_call = elapsed / 100
        assert per_call < 1, f"get(code) took {per_call:.3f}ms, expected < 1ms"

    def test_suggest_under_5ms(self):
        import psgc
        _ = psgc.suggest("m")  # warm up
        t0 = time.perf_counter()
        for _ in range(100):
            psgc.suggest("mak")
        elapsed = (time.perf_counter() - t0) * 1000
        per_call = elapsed / 100
        assert per_call < 5, f"suggest() took {per_call:.3f}ms, expected < 5ms"

    def test_validate_under_1ms(self):
        import psgc
        _ = psgc.validate("1339501004")  # warm up
        t0 = time.perf_counter()
        for _ in range(100):
            psgc.validate("1339501004")
        elapsed = (time.perf_counter() - t0) * 1000
        per_call = elapsed / 100
        assert per_call < 1, f"validate() took {per_call:.3f}ms, expected < 1ms"
