"""Merge centroid coordinates into the core data JSON files.

Reads centroids.json and updates barangays.json, cities.json, etc.
with coordinate and area data.

Usage:
    python -m parsers.compute_centroids --centroids psgc/data/spatial/centroids.json --data-dir psgc/data/core/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def merge_centroids(centroids_path: str, data_dir: str) -> None:
    """Merge centroids into core data files."""
    with open(centroids_path, encoding="utf-8") as f:
        centroids = json.load(f)

    core = Path(data_dir)
    _merge_into(core / "barangays.json", centroids, include_area=True)
    _merge_city_centroids(core / "cities.json", core / "barangays.json")
    _merge_province_centroids(core / "provinces.json", core / "cities.json")
    _merge_region_centroids(core / "regions.json", core / "provinces.json")


def _merge_into(json_path: Path, centroids: dict, include_area: bool = False) -> None:
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    matched = 0
    for entry in data:
        code = entry["psgc_code"]
        if code in centroids:
            c = centroids[code]
            entry["coordinate"] = {
                "latitude": c["latitude"],
                "longitude": c["longitude"],
            }
            if include_area and "area_km2" in c:
                entry["area_km2"] = c["area_km2"]
            matched += 1

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  {json_path.name}: matched {matched}/{len(data)} entries")


def _merge_city_centroids(cities_path: Path, barangays_path: Path) -> None:
    """Compute city centroids as average of their barangay centroids."""
    with open(barangays_path, encoding="utf-8") as f:
        barangays = json.load(f)

    city_coords: dict[str, list[tuple[float, float]]] = {}
    for b in barangays:
        coord = b.get("coordinate")
        if coord:
            city_code = b["city_code"]
            city_coords.setdefault(city_code, []).append(
                (coord["latitude"], coord["longitude"])
            )

    with open(cities_path, encoding="utf-8") as f:
        cities = json.load(f)

    for city in cities:
        if city.get("coordinate"):
            continue
        coords = city_coords.get(city["psgc_code"], [])
        if coords:
            avg_lat = sum(c[0] for c in coords) / len(coords)
            avg_lon = sum(c[1] for c in coords) / len(coords)
            city["coordinate"] = {
                "latitude": round(avg_lat, 6),
                "longitude": round(avg_lon, 6),
            }

    with open(cities_path, "w", encoding="utf-8") as f:
        json.dump(cities, f, ensure_ascii=False, indent=2)

    print(f"  cities.json: computed centroids from barangay averages")


def _merge_province_centroids(provinces_path: Path, cities_path: Path) -> None:
    """Compute province centroids as average of their city centroids."""
    with open(cities_path, encoding="utf-8") as f:
        cities = json.load(f)

    prov_coords: dict[str, list[tuple[float, float]]] = {}
    for c in cities:
        coord = c.get("coordinate")
        if coord:
            prov_code = c["province_code"]
            prov_coords.setdefault(prov_code, []).append(
                (coord["latitude"], coord["longitude"])
            )

    with open(provinces_path, encoding="utf-8") as f:
        provinces = json.load(f)

    for prov in provinces:
        if prov.get("coordinate"):
            continue
        coords = prov_coords.get(prov["psgc_code"], [])
        if coords:
            avg_lat = sum(c[0] for c in coords) / len(coords)
            avg_lon = sum(c[1] for c in coords) / len(coords)
            prov["coordinate"] = {
                "latitude": round(avg_lat, 6),
                "longitude": round(avg_lon, 6),
            }

    with open(provinces_path, "w", encoding="utf-8") as f:
        json.dump(provinces, f, ensure_ascii=False, indent=2)


def _merge_region_centroids(regions_path: Path, provinces_path: Path) -> None:
    """Compute region centroids as average of their province centroids."""
    with open(provinces_path, encoding="utf-8") as f:
        provinces = json.load(f)

    reg_coords: dict[str, list[tuple[float, float]]] = {}
    for p in provinces:
        coord = p.get("coordinate")
        if coord:
            reg_code = p["region_code"]
            reg_coords.setdefault(reg_code, []).append(
                (coord["latitude"], coord["longitude"])
            )

    with open(regions_path, encoding="utf-8") as f:
        regions = json.load(f)

    for reg in regions:
        if reg.get("coordinate"):
            continue
        coords = reg_coords.get(reg["psgc_code"], [])
        if coords:
            avg_lat = sum(c[0] for c in coords) / len(coords)
            avg_lon = sum(c[1] for c in coords) / len(coords)
            reg["coordinate"] = {
                "latitude": round(avg_lat, 6),
                "longitude": round(avg_lon, 6),
            }

    with open(regions_path, "w", encoding="utf-8") as f:
        json.dump(regions, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge centroids into core data")
    parser.add_argument("--centroids", default="psgc/data/spatial/centroids.json")
    parser.add_argument("--data-dir", default="psgc/data/core")
    args = parser.parse_args()
    merge_centroids(args.centroids, args.data_dir)
