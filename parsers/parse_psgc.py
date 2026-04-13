"""Parse the official PSGC masterlist Excel file from PSA.

Usage:
    python -m parsers.parse_psgc --input PSGC_masterlist.xlsx --output psgc/data/core/

Downloads the masterlist from:
    https://psa.gov.ph/classification/psgc
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ISLAND_GROUP_MAP = {
    "01": "luzon", "02": "luzon", "03": "luzon", "04": "luzon",
    "05": "luzon", "06": "visayas", "07": "visayas", "08": "visayas",
    "09": "mindanao", "10": "mindanao", "11": "mindanao", "12": "mindanao",
    "13": "luzon", "14": "luzon", "16": "mindanao", "17": "luzon",
    "19": "mindanao",
}

GEO_LEVELS = {
    "Reg": "region",
    "Prov": "province",
    "Dist": "province",
    "City": "city",
    "Mun": "municipality",
    "SubMun": "sub_municipality",
    "Bgy": "barangay",
}


def parse_masterlist(xlsx_path: str, output_dir: str) -> None:
    """Parse PSGC masterlist and output structured JSON files."""
    try:
        import openpyxl
    except ImportError:
        print("openpyxl required: pip install openpyxl")
        sys.exit(1)

    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb.active

    regions, provinces, cities, barangays = [], [], [], []

    current_region = None
    current_province = None
    current_city = None

    for row in ws.iter_rows(min_row=2, values_only=True):
        if len(row) < 6:
            continue

        code = str(row[0] or "").strip()
        name = str(row[1] or "").strip()
        corr_code = str(row[2] or "").strip()
        geo_level = str(row[3] or "").strip()
        old_names = str(row[4] or "").strip()
        city_class = str(row[5] or "").strip() if len(row) > 5 else ""
        income_class = str(row[6] or "").strip() if len(row) > 6 else ""
        urban_rural = str(row[7] or "").strip() if len(row) > 7 else ""
        population = row[8] if len(row) > 8 else None

        if not code or not name:
            continue

        pop_int = _parse_population(population)
        region_prefix = code[:2]
        island_group = ISLAND_GROUP_MAP.get(region_prefix)

        if geo_level == "Reg":
            entry = {
                "psgc_code": code, "name": name,
                "island_group": island_group,
                "population": pop_int,
                "coordinate": None,
            }
            regions.append(entry)
            current_region = code

        elif geo_level in ("Prov", "Dist"):
            entry = {
                "psgc_code": code, "name": name,
                "region_code": current_region,
                "island_group": island_group,
                "income_classification": income_class or None,
                "population": pop_int,
                "coordinate": None,
            }
            provinces.append(entry)
            current_province = code

        elif geo_level in ("City", "Mun", "SubMun"):
            entry = {
                "psgc_code": code, "name": name,
                "province_code": current_province,
                "region_code": current_region,
                "geographic_level": geo_level,
                "city_class": city_class or None,
                "income_classification": income_class or None,
                "urban_rural": urban_rural or None,
                "population": pop_int,
                "coordinate": None,
            }
            cities.append(entry)
            current_city = code

        elif geo_level == "Bgy":
            entry = {
                "psgc_code": code, "name": name,
                "city_code": current_city,
                "province_code": current_province,
                "region_code": current_region,
                "urban_rural": urban_rural or None,
                "population": pop_int,
                "coordinate": None,
                "zip_code": None,
                "area_km2": None,
            }
            barangays.append(entry)

    wb.close()

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    _write_json(out / "regions.json", regions)
    _write_json(out / "provinces.json", provinces)
    _write_json(out / "cities.json", cities)
    _write_json(out / "barangays.json", barangays)

    print(f"Parsed: {len(regions)} regions, {len(provinces)} provinces, "
          f"{len(cities)} cities, {len(barangays)} barangays")


def _parse_population(val) -> int | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    cleaned = re.sub(r"[,\s]", "", str(val))
    try:
        return int(cleaned)
    except ValueError:
        return None


def _write_json(path: Path, data: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Wrote {path} ({len(data)} entries)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse PSGC masterlist")
    parser.add_argument("--input", required=True, help="Path to PSGC Excel file")
    parser.add_argument("--output", default="psgc/data/core", help="Output directory")
    args = parser.parse_args()
    parse_masterlist(args.input, args.output)
