"""Tests for geographic/spatial features."""

from __future__ import annotations

import pytest


class TestDistance:
    def test_haversine(self):
        from psgc.geo.distance import haversine
        dist = haversine(14.5833, 120.9822, 14.5896, 120.9750)
        assert 0.5 < dist < 2.0  # Ermita to Intramuros ~1km

    def test_haversine_same_point(self):
        from psgc.geo.distance import haversine
        dist = haversine(14.5, 120.9, 14.5, 120.9)
        assert dist == 0.0

    def test_vincenty(self):
        from psgc.geo.distance import haversine, vincenty
        h = haversine(14.5833, 120.9822, 10.3157, 123.8854)
        v = vincenty(14.5833, 120.9822, 10.3157, 123.8854)
        # Vincenty and Haversine should agree within 1%
        assert abs(h - v) / h < 0.01


class TestPointInPolygon:
    def test_inside_square(self):
        from psgc.geo.pip import point_in_polygon
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        assert point_in_polygon(5, 5, square) is True

    def test_outside_square(self):
        from psgc.geo.pip import point_in_polygon
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        assert point_in_polygon(15, 15, square) is False

    def test_triangle(self):
        from psgc.geo.pip import point_in_polygon
        triangle = [(0, 0), (10, 0), (5, 10)]
        assert point_in_polygon(5, 3, triangle) is True
        assert point_in_polygon(0, 10, triangle) is False

    def test_multipolygon(self):
        from psgc.geo.pip import point_in_multipolygon
        polys = [
            [(0, 0), (5, 0), (5, 5), (0, 5)],
            [(10, 10), (15, 10), (15, 15), (10, 15)],
        ]
        assert point_in_multipolygon(3, 3, polys) is True
        assert point_in_multipolygon(12, 12, polys) is True
        assert point_in_multipolygon(7, 7, polys) is False


class TestSpatialIndex:
    def test_nearest(self):
        from psgc.geo.spatial import get_spatial_index
        results = get_spatial_index().nearest(14.5995, 120.9842, n=3)
        assert len(results) == 3
        from psgc.results import NearestResult
        assert all(isinstance(r, NearestResult) for r in results)
        r = results[0]
        brgy, dist = r.place, r.distance_km
        assert dist < 5.0  # within 5km

    def test_within_radius(self):
        from psgc.geo.spatial import get_spatial_index
        results = get_spatial_index().within_radius(14.5995, 120.9842, radius_km=2.0)
        assert len(results) > 0
        for r in results:
            assert r.distance_km <= 2.0

    def test_within_radius_sorted(self):
        from psgc.geo.spatial import get_spatial_index
        results = get_spatial_index().within_radius(14.5995, 120.9842, radius_km=10.0)
        distances = [r.distance_km for r in results]
        assert distances == sorted(distances)


class TestReverseGeocode:
    def test_basic(self):
        from psgc.geo.reverse import reverse_geocode
        result = reverse_geocode(14.5833, 120.9822)
        assert result.barangay
        assert result.city
        assert result.province
        assert result.region

    def test_returns_method(self):
        from psgc.geo.reverse import reverse_geocode
        result = reverse_geocode(14.5833, 120.9822)
        assert result.method in ("centroid", "boundary")
