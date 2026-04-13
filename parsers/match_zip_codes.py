"""Match ZIP codes to PSGC cities/barangays.

Source: https://github.com/simonpangan/Philippines-Zip-Codes

Usage:
    python -m parsers.match_zip_codes --input zip_codes.sql --output psgc/data/core/zip_codes.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def parse_zip_codes(input_path: str, output_path: str) -> None:
    """Parse ZIP code data from MySQL dump or CSV."""
    inp = Path(input_path)
    suffix = inp.suffix.lower()

    if suffix == ".sql":
        entries = _parse_sql(inp)
    elif suffix == ".csv":
        entries = _parse_csv(inp)
    else:
        print(f"Unsupported format: {suffix} (use .sql or .csv)")
        sys.exit(1)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"Parsed {len(entries)} ZIP code entries -> {out}")


def _parse_sql(path: Path) -> dict:
    """Parse INSERT statements from MySQL dump."""
    content = path.read_text(encoding="utf-8", errors="replace")

    insert_pattern = re.compile(
        r"INSERT\s+INTO\s+.*?VALUES\s*(.+?);",
        re.IGNORECASE | re.DOTALL,
    )

    entries: dict[str, dict] = {}

    for match in insert_pattern.finditer(content):
        values_block = match.group(1)
        row_pattern = re.compile(r"\(([^)]+)\)")
        for row_match in row_pattern.finditer(values_block):
            fields = _parse_sql_row(row_match.group(1))
            if len(fields) >= 3:
                zip_code = fields[0].strip().strip("'\"")
                area = fields[1].strip().strip("'\"")
                city = fields[2].strip().strip("'\"")
                province = fields[3].strip().strip("'\"")

                if zip_code.isdigit() and len(zip_code) == 4:
                    entries[zip_code] = {
                        "area": area,
                        "city": city,
                        "province": province,
                    }

    return entries


def _parse_sql_row(row: str) -> list[str]:
    """Parse a comma-separated SQL row respecting quotes."""
    fields: list[str] = []
    current = ""
    in_quote = False
    quote_char = ""

    for char in row:
        if not in_quote and char in ("'", '"'):
            in_quote = True
            quote_char = char
            current += char
        elif in_quote and char == quote_char:
            in_quote = False
            current += char
        elif not in_quote and char == ",":
            fields.append(current.strip())
            current = ""
        else:
            current += char

    if current.strip():
        fields.append(current.strip())

    return fields


def _parse_csv(path: Path) -> dict:
    """Parse ZIP codes from CSV."""
    import csv

    entries: dict[str, dict] = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            zip_code = row.get("zip_code", row.get("ZipCode", "")).strip()
            area = row.get("area", row.get("Area", "")).strip()
            city = row.get("city", row.get("City", "")).strip()
            province = row.get("province", row.get("Province", "")).strip()

            if zip_code.isdigit() and len(zip_code) == 4:
                entries[zip_code] = {
                    "area": area,
                    "city": city,
                    "province": province,
                }

    return entries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse ZIP code data")
    parser.add_argument("--input", required=True, help="SQL dump or CSV file")
    parser.add_argument("--output", default="psgc/data/core/zip_codes.json")
    args = parser.parse_args()
    parse_zip_codes(args.input, args.output)
