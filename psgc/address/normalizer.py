"""Filipino address normalization and abbreviation handling."""

from __future__ import annotations

import re

ABBREVIATIONS: dict[str, str] = {
    "brgy": "barangay",
    "brgy.": "barangay",
    "bgy": "barangay",
    "bgy.": "barangay",
    "bgry": "barangay",
    "bgry.": "barangay",
    "mun": "municipality",
    "mun.": "municipality",
    "prov": "province",
    "prov.": "province",
    "st": "street",
    "st.": "street",
    "ave": "avenue",
    "ave.": "avenue",
    "blvd": "boulevard",
    "blvd.": "boulevard",
    "dr": "drive",
    "dr.": "drive",
    "rd": "road",
    "rd.": "road",
    "cor": "corner",
    "cor.": "corner",
    "nr": "near",
    "nr.": "near",
    "opp": "opposite",
    "opp.": "opposite",
    "bldg": "building",
    "bldg.": "building",
    "flr": "floor",
    "flr.": "floor",
    "rm": "room",
    "rm.": "room",
    "govt": "government",
    "govt.": "government",
    "natl": "national",
    "natl.": "national",
    "gen": "general",
    "gen.": "general",
}

_CITY_PREFIXES = [
    "city of ",
    "municipality of ",
    "mun. of ",
    "mun of ",
]


def normalize_name(name: str) -> str:
    """Normalize a geographic name for matching."""
    result = name.strip()

    for prefix in _CITY_PREFIXES:
        if result.lower().startswith(prefix):
            result = result[len(prefix):]
            break

    if result.lower().endswith(" city"):
        result = result[: -len(" city")]

    result = re.sub(r"\s*\(.*?\)\s*", " ", result)
    result = re.sub(r"\s+", " ", result).strip()

    return result


def expand_abbreviations(text: str) -> str:
    """Expand common Filipino address abbreviations."""
    words = text.split()
    expanded: list[str] = []
    for word in words:
        lower = word.lower().rstrip(".,")
        key_with_dot = lower + "."
        if lower in ABBREVIATIONS:
            expanded.append(ABBREVIATIONS[lower])
        elif key_with_dot in ABBREVIATIONS:
            expanded.append(ABBREVIATIONS[key_with_dot])
        else:
            expanded.append(word)
    return " ".join(expanded)


def sanitize_input(text: str, exclude: list[str] | None = None) -> str:
    """Clean and normalize input text for search."""
    result = text.lower().strip()
    if exclude:
        for word in exclude:
            result = result.replace(word.lower(), "")
    result = re.sub(r"[^\w\s,.-]", "", result)
    result = re.sub(r"\s+", " ", result).strip()
    return result
