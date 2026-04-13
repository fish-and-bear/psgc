"""Spatial index using KD-tree for fast nearest-neighbor queries."""

from __future__ import annotations

import logging
import math
import time
from typing import Any

from psgc._loader import get_store
from psgc.geo.distance import EARTH_RADIUS_KM, haversine
from psgc.models.barangay import Barangay
from psgc.results import NearestResult

log = logging.getLogger(__name__)

PH_LAT_MIN, PH_LAT_MAX = 4.0, 21.5
PH_LNG_MIN, PH_LNG_MAX = 116.0, 127.5


def _warn_if_outside_ph(latitude: float, longitude: float) -> None:
    """Log a warning if coordinates are outside the Philippines bounding box."""
    if math.isnan(latitude) or math.isnan(longitude) or math.isinf(latitude) or math.isinf(longitude):
        raise ValueError(f"Coordinates must be finite numbers, got ({latitude}, {longitude})")
    if not (PH_LAT_MIN <= latitude <= PH_LAT_MAX) or not (PH_LNG_MIN <= longitude <= PH_LNG_MAX):
        if PH_LAT_MIN <= longitude <= PH_LAT_MAX and PH_LNG_MIN <= latitude <= PH_LNG_MAX:
            log.warning(
                "Coordinates (%.4f, %.4f) appear to have lat/lng swapped. "
                "Expected nearest(latitude, longitude), not nearest(longitude, latitude).",
                latitude, longitude,
            )
        else:
            log.warning(
                "Coordinates (%.4f, %.4f) are outside the Philippines (lat %.1f-%.1f, lng %.1f-%.1f). "
                "Results may not be meaningful.",
                latitude, longitude, PH_LAT_MIN, PH_LAT_MAX, PH_LNG_MIN, PH_LNG_MAX,
            )


class SpatialIndex:
    """KD-tree spatial index over barangay centroids.

    Lazily imports scipy on first use.
    """

    def __init__(self) -> None:
        self._tree: Any = None
        self._barangays: list[Barangay] = []
        self._coords: list[tuple[float, float, float]] = []

    def _ensure_built(self) -> None:
        if self._tree is not None:
            return

        log.info("Building spatial KD-tree index...")
        t0 = time.perf_counter()

        from psgc._lazy import lazy_import
        scipy_spatial = lazy_import("scipy.spatial")

        store = get_store()
        self._barangays = []
        cartesian: list[list[float]] = []

        for b in store.barangays:
            if b.coordinate is None:
                continue
            self._barangays.append(b)
            lat_r = math.radians(b.coordinate.latitude)
            lon_r = math.radians(b.coordinate.longitude)
            x = EARTH_RADIUS_KM * math.cos(lat_r) * math.cos(lon_r)
            y = EARTH_RADIUS_KM * math.cos(lat_r) * math.sin(lon_r)
            z = EARTH_RADIUS_KM * math.sin(lat_r)
            cartesian.append([x, y, z])

        if not cartesian:
            log.warning("No barangays with coordinates found; spatial queries will return empty results")
            self._tree = None
            return

        self._tree = scipy_spatial.KDTree(cartesian)
        elapsed = (time.perf_counter() - t0) * 1000
        log.info("KD-tree built: %d points in %.1fms", len(self._barangays), elapsed)

    def nearest(
        self, latitude: float, longitude: float, n: int = 5
    ) -> list[NearestResult]:
        """Find N nearest barangays to a point.

        Returns list of NearestResult with .place and .distance_km.
        """
        _warn_if_outside_ph(latitude, longitude)
        if n <= 0:
            return []
        self._ensure_built()
        if self._tree is None or not self._barangays:
            return []

        lat_r = math.radians(latitude)
        lon_r = math.radians(longitude)
        x = EARTH_RADIUS_KM * math.cos(lat_r) * math.cos(lon_r)
        y = EARTH_RADIUS_KM * math.cos(lat_r) * math.sin(lon_r)
        z = EARTH_RADIUS_KM * math.sin(lat_r)

        distances, indices = self._tree.query([x, y, z], k=min(n, len(self._barangays)))

        if n == 1:
            distances = [distances]
            indices = [indices]

        results: list[NearestResult] = []
        for _, idx in zip(distances, indices):
            b = self._barangays[idx]
            dist = haversine(
                latitude, longitude,
                b.coordinate.latitude, b.coordinate.longitude  # type: ignore
            )
            results.append(NearestResult(place=b, distance_km=round(dist, 3)))

        log.debug("nearest(%.4f, %.4f, n=%d) -> %d results, closest=%s (%.3f km)",
                  latitude, longitude, n, len(results),
                  results[0].name if results else "none",
                  results[0].distance_km if results else 0)
        return results

    def within_radius(
        self, latitude: float, longitude: float, radius_km: float
    ) -> list[NearestResult]:
        """Find all barangays within a radius (km) of a point."""
        _warn_if_outside_ph(latitude, longitude)
        self._ensure_built()
        if self._tree is None or not self._barangays:
            return []

        lat_r = math.radians(latitude)
        lon_r = math.radians(longitude)
        x = EARTH_RADIUS_KM * math.cos(lat_r) * math.cos(lon_r)
        y = EARTH_RADIUS_KM * math.cos(lat_r) * math.sin(lon_r)
        z = EARTH_RADIUS_KM * math.sin(lat_r)

        chord_dist = 2 * EARTH_RADIUS_KM * math.sin(radius_km / (2 * EARTH_RADIUS_KM))
        indices = self._tree.query_ball_point([x, y, z], chord_dist)

        results: list[NearestResult] = []
        for idx in indices:
            b = self._barangays[idx]
            dist = haversine(
                latitude, longitude,
                b.coordinate.latitude, b.coordinate.longitude  # type: ignore
            )
            if dist <= radius_km:
                results.append(NearestResult(place=b, distance_km=round(dist, 3)))

        results.sort(key=lambda r: r.distance_km)
        log.debug("within_radius(%.4f, %.4f, r=%.1f km) -> %d results",
                  latitude, longitude, radius_km, len(results))
        return results


_spatial_index: SpatialIndex | None = None


def get_spatial_index() -> SpatialIndex:
    """Return the singleton SpatialIndex, creating it on first call."""
    global _spatial_index
    if _spatial_index is None:
        _spatial_index = SpatialIndex()
    return _spatial_index
