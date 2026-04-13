"""GeoJSON export for Philippine geographic data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from psgc._loader import get_store


def _point_feature(name: str, lat: float, lon: float, properties: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"name": name, **properties},
    }


def to_geojson(
    level: str = "barangay",
    region: str | None = None,
    province: str | None = None,
    city: str | None = None,
    output: str | Path | None = None,
    as_dict: bool = False,
) -> dict[str, Any] | str:
    """Export geographic data as GeoJSON FeatureCollection.

    Args:
        level: Geographic level to export (region/province/city/barangay)
        region: Filter by region name
        province: Filter by province name
        city: Filter by city name
        output: File path to write GeoJSON
        as_dict: Return as Python dict instead of JSON string

    Returns:
        GeoJSON as dict or string, or writes to file.
    """
    store = get_store()
    features: list[dict] = []

    if level == "region":
        for r in store.regions:
            if region and region.lower() not in r.name.lower():
                continue
            if r.coordinate:
                features.append(_point_feature(r.name, r.coordinate.latitude, r.coordinate.longitude, {
                    "psgc_code": r.psgc_code,
                    "level": "region",
                    "island_group": r.island_group.value if r.island_group else None,
                    "population": r.population,
                }))

    elif level == "province":
        for p in store.provinces:
            if region:
                r = store.get_region(p.region_code)
                if region.lower() not in r.name.lower():
                    continue
            if province and province.lower() not in p.name.lower():
                continue
            if p.coordinate:
                features.append(_point_feature(p.name, p.coordinate.latitude, p.coordinate.longitude, {
                    "psgc_code": p.psgc_code,
                    "level": "province",
                    "region": store.get_region(p.region_code).name,
                    "island_group": p.island_group.value if p.island_group else None,
                    "income_classification": p.income_classification,
                    "population": p.population,
                }))

    elif level == "city":
        for c in store.cities:
            if region:
                r = store.get_region(c.region_code)
                if region.lower() not in r.name.lower():
                    continue
            if province:
                p = store.get_province(c.province_code)
                if province.lower() not in p.name.lower():
                    continue
            if city and city.lower() not in c.name.lower():
                continue
            if c.coordinate:
                features.append(_point_feature(c.name, c.coordinate.latitude, c.coordinate.longitude, {
                    "psgc_code": c.psgc_code,
                    "level": "city",
                    "province": store.get_province(c.province_code).name,
                    "region": store.get_region(c.region_code).name,
                    "city_class": c.city_class,
                    "income_classification": c.income_classification,
                    "population": c.population,
                }))

    else:  # barangay
        for b in store.barangays:
            if region:
                r = store.get_region(b.region_code)
                if region.lower() not in r.name.lower():
                    continue
            if province:
                p = store.get_province(b.province_code)
                if province.lower() not in p.name.lower():
                    continue
            if city:
                c = store.get_city(b.city_code)
                if city.lower() not in c.name.lower():
                    continue
            if b.coordinate:
                c_obj = store.get_city(b.city_code)
                features.append(_point_feature(b.name, b.coordinate.latitude, b.coordinate.longitude, {
                    "psgc_code": b.psgc_code,
                    "level": "barangay",
                    "city": c_obj.name,
                    "province": store.get_province(b.province_code).name,
                    "region": store.get_region(b.region_code).name,
                    "urban_rural": b.urban_rural,
                    "population": b.population,
                    "zip_code": b.zip_code,
                    "area_km2": b.area_km2,
                }))

    fc: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": features,
    }

    if output:
        p = Path(output)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(fc, f, ensure_ascii=False, indent=2)
        return str(p)

    if as_dict:
        return fc

    return json.dumps(fc, ensure_ascii=False, indent=2)
