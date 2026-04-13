"""Export geographic data in CSV, JSON, and YAML formats."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from psgc._loader import get_store


def _flat_data(
    level: str | None = None,
    region: str | None = None,
    province: str | None = None,
    island_group: str | None = None,
) -> list[dict[str, Any]]:
    store = get_store()
    items = store.build_flat()

    if level:
        level_map = {
            "region": "Reg", "province": "Prov", "city": "City",
            "municipality": "Mun", "barangay": "Bgy",
        }
        level_code = level_map.get(level.lower(), level)
        items = [i for i in items if i.level.value == level_code]

    if region:
        items = [i for i in items if i.region_name and region.lower() in i.region_name.lower()]
    if province:
        items = [i for i in items if i.province_name and province.lower() in i.province_name.lower()]
    if island_group:
        items = [
            i for i in items
            if i.island_group and island_group.lower() == i.island_group.value.lower()
        ]

    return [i.to_dict() for i in items]


def to_csv(
    level: str | None = None,
    region: str | None = None,
    province: str | None = None,
    island_group: str | None = None,
    output: str | Path | None = None,
) -> str:
    """Export data as CSV."""
    data = _flat_data(level, region, province, island_group)
    if not data:
        return ""

    fieldnames = list(data[0].keys())
    for item in data:
        for key in item.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    if "coordinate" in fieldnames:
        fieldnames.remove("coordinate")
        if "latitude" not in fieldnames:
            fieldnames.extend(["latitude", "longitude"])

    rows: list[dict[str, Any]] = []
    for item in data:
        row = dict(item)
        coord = row.pop("coordinate", None)
        if coord:
            row["latitude"] = coord.get("latitude")
            row["longitude"] = coord.get("longitude")
        rows.append(row)

    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    result = buf.getvalue()

    if output:
        p = Path(output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(result, encoding="utf-8")

    return result


def to_json(
    level: str | None = None,
    region: str | None = None,
    province: str | None = None,
    island_group: str | None = None,
    output: str | Path | None = None,
    indent: int = 2,
) -> str:
    """Export data as JSON."""
    data = _flat_data(level, region, province, island_group)
    result = json.dumps(data, ensure_ascii=False, indent=indent)

    if output:
        p = Path(output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(result, encoding="utf-8")

    return result


def to_yaml(
    level: str | None = None,
    region: str | None = None,
    province: str | None = None,
    island_group: str | None = None,
    output: str | Path | None = None,
) -> str:
    """Export data as YAML. Requires pyyaml."""
    try:
        import yaml
    except ImportError:
        raise ImportError(
            "pyyaml is required for YAML export. "
            "Install it with: pip install pyyaml"
        ) from None

    data = _flat_data(level, region, province, island_group)
    result = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)

    if output:
        p = Path(output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(result, encoding="utf-8")

    return result
