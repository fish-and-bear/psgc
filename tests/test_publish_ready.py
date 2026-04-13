"""Pre-publish checklist tests."""

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


class TestPackaging:
    def test_data_files_exist(self):
        """Verify data files are in the package directory."""
        import psgc
        pkg = Path(psgc.__file__).parent
        assert (pkg / "data" / "core" / "regions.json").exists()
        assert (pkg / "data" / "core" / "barangays.json").exists()
        assert (pkg / "data" / "core" / "cities.json").exists()
        assert (pkg / "py.typed").exists()

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
        assert "psgc" in names

    def test_only_one_runtime_dependency(self):
        from importlib.metadata import requires
        reqs = requires("psgc") or []
        core_reqs = [r for r in reqs if "extra" not in r]
        assert len(core_reqs) == 1
        assert "rapidfuzz" in core_reqs[0]


class TestSecurity:
    def test_search_doesnt_eval_input(self):
        import psgc
        dangerous_inputs = [
            "__import__('os').system('echo pwned')",
            "{{7*7}}",
            "${7*7}",
            "'; DROP TABLE barangays; --",
            "../../../etc/passwd",
        ]
        for inp in dangerous_inputs:
            results = psgc.search(inp, threshold=10)
            assert isinstance(results, list)

    def test_no_pickle_usage(self):
        import psgc
        pkg_dir = Path(psgc.__file__).parent
        for py_file in pkg_dir.rglob("*.py"):
            content = py_file.read_text()
            assert "pickle" not in content.lower() or "# safe" in content

    def test_no_eval_or_exec(self):
        import psgc
        pkg_dir = Path(psgc.__file__).parent
        for py_file in pkg_dir.rglob("*.py"):
            content = py_file.read_text()
            for line_num, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                assert "eval(" not in stripped
                assert "exec(" not in stripped

    def test_no_subprocess_usage(self):
        import psgc
        pkg_dir = Path(psgc.__file__).parent
        for py_file in pkg_dir.rglob("*.py"):
            content = py_file.read_text()
            assert "subprocess" not in content
            assert "os.system" not in content


class TestAPIStability:
    def test_public_api_surface(self):
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


class TestBugHunting:
    def test_get_then_navigate_full_chain(self):
        import psgc
        from psgc._loader import get_store
        b = get_store().barangays[0]
        city = b.parent
        province = city.parent
        region = province.parent
        assert region.psgc_code == b.region_code

    def test_search_then_get_same_place(self):
        import psgc
        results = psgc.search("Quezon City", n=1)
        sr = results[0]
        place = psgc.get(sr.psgc_code)
        assert place.psgc_code == sr.psgc_code

    def test_to_dict_roundtrip_json_safe(self):
        import psgc
        for b in psgc.barangays:
            d = b.to_dict()
            json_str = json.dumps(d)
            parsed = json.loads(json_str)
            assert parsed["psgc_code"] == b.psgc_code

    def test_flat_and_tree_contain_same_data(self):
        import psgc
        flat_codes = {f.psgc_code for f in psgc.flat}
        tree_nodes = []
        for t in psgc.tree:
            tree_nodes.extend(t.flatten())
        tree_codes = {n.psgc_code for n in tree_nodes}
        assert flat_codes == tree_codes

    def test_multiple_gets_return_same_object(self):
        import psgc
        from psgc._loader import get_store
        code = get_store().barangays[0].psgc_code
        a = psgc.get(code)
        b = psgc.get(code)
        assert a is b

    def test_parent_child_identity(self):
        import psgc
        b = psgc.barangays[0]
        children = b.parent.children
        found = [c for c in children if c.psgc_code == b.psgc_code]
        assert len(found) == 1
        assert found[0] is b


class TestPerformanceRegression:
    def test_search_under_200ms(self):
        import psgc
        _ = psgc.search("warmup")
        t0 = time.perf_counter()
        for _ in range(10):
            psgc.search("Manila", n=5)
        elapsed = (time.perf_counter() - t0) * 1000
        per_call = elapsed / 10
        assert per_call < 200

    def test_get_by_code_under_5ms(self):
        import psgc
        from psgc._loader import get_store
        code = get_store().barangays[0].psgc_code
        _ = psgc.get(code)
        t0 = time.perf_counter()
        for _ in range(100):
            psgc.get(code)
        elapsed = (time.perf_counter() - t0) * 1000
        per_call = elapsed / 100
        assert per_call < 5

    def test_suggest_under_5ms(self):
        import psgc
        _ = psgc.suggest("m")
        t0 = time.perf_counter()
        for _ in range(100):
            psgc.suggest("mak")
        elapsed = (time.perf_counter() - t0) * 1000
        per_call = elapsed / 100
        assert per_call < 5
