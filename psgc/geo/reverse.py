"""Reverse geocoding: coordinates to barangay/city/province."""

from __future__ import annotations

import json
import logging
from typing import Any

from psgc._loader import get_store
from psgc.config import config
from psgc.geo.pip import point_in_multipolygon, point_in_polygon
from psgc.geo.spatial import get_spatial_index
from psgc.models.barangay import Barangay
from psgc.results import GeocodeResult

log = logging.getLogger(__name__)


def reverse_geocode(
    latitude: float,
    longitude: float,
    use_boundaries: bool = True,
) -> GeocodeResult:
    """Reverse geocode a lat/lng point to its containing barangay.

    First attempts point-in-polygon against boundary data.
    Falls back to nearest-centroid if no boundary match is found.

    Args:
        latitude: Latitude (WGS84)
        longitude: Longitude (WGS84)
        use_boundaries: Try polygon containment before centroid fallback

    Returns:
        GeocodeResult with .place (Barangay), .distance_km, .method,
        plus convenience properties .barangay, .city, .province, .region.
    """
    from psgc.geo.spatial import _warn_if_outside_ph
    _warn_if_outside_ph(latitude, longitude)
    log.debug("Reverse geocoding (%.4f, %.4f), use_boundaries=%s", latitude, longitude, use_boundaries)
    store = get_store()

    if use_boundaries:
        match = _try_boundary_match(latitude, longitude)
        if match is not None:
            log.debug("Boundary match found: %s", match.name)
            return GeocodeResult(place=match, distance_km=0.0, method="boundary")
        log.debug("No boundary match, falling back to centroid")

    results = get_spatial_index().nearest(latitude, longitude, n=1)
    if results:
        r = results[0]
        log.debug("Centroid match: %s (%.3f km)", r.name, r.distance_km)
        return GeocodeResult(place=r.place, distance_km=r.distance_km, method="centroid")

    log.warning("Reverse geocode failed: no data for (%.4f, %.4f)", latitude, longitude)
    raise LookupError(f"No geographic data available for ({latitude}, {longitude})")


def _try_boundary_match(lat: float, lng: float) -> Barangay | None:
    """Try to find which barangay polygon contains the point."""
    boundary_dir = config.boundary_dir / "barangays"
    if not boundary_dir.exists():
        return None

    store = get_store()

    for geojson_file in boundary_dir.glob("*.geojson"):
        try:
            with open(geojson_file, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        features = data.get("features", [data]) if "features" in data else [data]
        for feature in features:
            geom = feature.get("geometry", {})
            props = feature.get("properties", {})
            psgc_code = props.get("psgc_code", "")

            coords = geom.get("coordinates", [])
            geom_type = geom.get("type", "")

            hit = False
            if geom_type == "Polygon" and coords:
                ring = [(c[0], c[1]) for c in coords[0]]
                hit = point_in_polygon(lng, lat, ring)
            elif geom_type == "MultiPolygon":
                rings = [[(c[0], c[1]) for c in poly[0]] for poly in coords if poly]
                hit = point_in_multipolygon(lng, lat, rings)

            if hit:
                try:
                    return store.get_barangay(psgc_code)
                except KeyError:
                    pass
    return None
