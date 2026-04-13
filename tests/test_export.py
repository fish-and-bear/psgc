"""Tests for export functionality."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path


class TestGeoJSON:
    def test_basic_export(self):
        from psgc.export.geojson import to_geojson
        result = to_geojson(level="region", as_dict=True)
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) > 0

    def test_barangay_export(self):
        from psgc.export.geojson import to_geojson
        result = to_geojson(level="barangay", as_dict=True)
        assert len(result["features"]) > 0
        feat = result["features"][0]
        assert feat["geometry"]["type"] == "Point"
        assert "coordinates" in feat["geometry"]

    def test_region_filter(self):
        from psgc.export.geojson import to_geojson
        result = to_geojson(level="barangay", region="NCR", as_dict=True)
        for feat in result["features"]:
            assert "NCR" in feat["properties"]["region"]

    def test_file_output(self):
        from psgc.export.geojson import to_geojson
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.geojson"
            to_geojson(level="region", output=str(path))
            assert path.exists()
            data = json.loads(path.read_text())
            assert data["type"] == "FeatureCollection"

    def test_json_string_output(self):
        from psgc.export.geojson import to_geojson
        result = to_geojson(level="region")
        assert isinstance(result, str)
        data = json.loads(result)
        assert data["type"] == "FeatureCollection"


class TestCSV:
    def test_basic_csv(self):
        from psgc.export.formats import to_csv
        result = to_csv(level="region")
        assert len(result) > 0
        lines = result.strip().split("\n")
        assert len(lines) > 1  # header + data
        assert "psgc_code" in lines[0]

    def test_csv_with_filter(self):
        from psgc.export.formats import to_csv
        result = to_csv(level="barangay", region="NCR")
        assert len(result) > 0

    def test_csv_file_output(self):
        from psgc.export.formats import to_csv
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.csv"
            to_csv(level="region", output=str(path))
            assert path.exists()


class TestJSON:
    def test_basic_json(self):
        from psgc.export.formats import to_json
        result = to_json(level="region")
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_json_level_filter(self):
        from psgc.export.formats import to_json
        result = to_json(level="barangay")
        data = json.loads(result)
        assert all(d["level"] == "Bgy" for d in data)


class TestYAML:
    def test_basic_yaml(self):
        from psgc.export.formats import to_yaml
        result = to_yaml(level="region")
        assert len(result) > 0
        assert "psgc_code" in result
