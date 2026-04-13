"""Filipino address parser: extract barangay, city, province from unstructured text."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from psgc.address.normalizer import expand_abbreviations

log = logging.getLogger(__name__)


@dataclass
class ParsedAddress:
    """Result of parsing a Filipino address string."""

    raw: str
    street: Optional[str] = None
    barangay: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    region: Optional[str] = None
    zip_code: Optional[str] = None
    psgc_match: Optional[dict[str, Any]] = None
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "street": self.street,
            "barangay": self.barangay,
            "city": self.city,
            "province": self.province,
            "region": self.region,
            "zip_code": self.zip_code,
            "confidence": self.confidence,
            "psgc_match": self.psgc_match,
        }


_BARANGAY_PATTERN = re.compile(
    r"(?:brgy\.?|bgy\.?|bgry\.?|barangay)\s+"
    r"([\w\s\-.'()]+?)(?:\s*,|\s*$)",
    re.IGNORECASE,
)

_NUMBERED_BRGY_PATTERN = re.compile(
    r"(?:brgy\.?|bgy\.?|barangay)\s+(\d+(?:\s*-?\s*[a-zA-Z])?)",
    re.IGNORECASE,
)

_ZIP_PATTERN = re.compile(r"\b(\d{4})\b")

_CITY_INDICATORS = re.compile(
    r"(?:city\s+of\s+|municipality\s+of\s+)([\w\s\-.']+?)(?:\s*,|\s*$)",
    re.IGNORECASE,
)

_CITY_SUFFIX_PATTERN = re.compile(
    r"([\w\s\-.']+?)\s+city(?:\s*,|\s*$)",
    re.IGNORECASE,
)


def parse_address(address: str) -> ParsedAddress:
    """Parse an unstructured Filipino address into components.

    Handles common formats like:
    - "123 Rizal St., Brgy. San Antonio, Makati City"
    - "Barangay 123, City of Manila"
    - "Tondo, Manila, Metro Manila 1012"
    """
    MAX_ADDR_LEN = 500
    if len(address) > MAX_ADDR_LEN:
        address = address[:MAX_ADDR_LEN]
        log.debug("Address truncated to %d characters", MAX_ADDR_LEN)

    result = ParsedAddress(raw=address)
    expanded = expand_abbreviations(address)
    parts = [p.strip() for p in expanded.split(",")]

    _extract_zip(result, address)
    log.debug("Parsing address: %r", address)
    _extract_barangay(result, expanded)
    _extract_city(result, expanded, parts)
    _extract_province(result, parts)
    _extract_street(result, parts)
    if result.barangay is None and len(parts) >= 2:
        _try_barangay_fallback(result, parts)
    _fuzzy_match(result)

    log.debug("Parsed -> brgy=%s, city=%s, province=%s, zip=%s, confidence=%.0f%%",
              result.barangay, result.city, result.province, result.zip_code,
              result.confidence * 100)
    return result


def _extract_zip(result: ParsedAddress, text: str) -> None:
    match = _ZIP_PATTERN.search(text)
    if match:
        zip_code = match.group(1)
        if 400 <= int(zip_code) <= 9900:
            result.zip_code = zip_code


def _extract_barangay(result: ParsedAddress, text: str) -> None:
    match = _NUMBERED_BRGY_PATTERN.search(text)
    if match:
        result.barangay = f"Barangay {match.group(1).strip()}"
        return

    match = _BARANGAY_PATTERN.search(text)
    if match:
        result.barangay = match.group(1).strip().rstrip(",")
        return


def _extract_city(result: ParsedAddress, text: str, parts: list[str]) -> None:
    match = _CITY_INDICATORS.search(text)
    if match:
        result.city = match.group(1).strip()
        return

    match = _CITY_SUFFIX_PATTERN.search(text)
    if match:
        result.city = f"{match.group(1).strip()} City"
        return

    if len(parts) >= 2:
        candidate = parts[-2] if len(parts) >= 3 else parts[-1]
        candidate = candidate.strip()
        candidate = re.sub(r"\s*\d{4}\s*$", "", candidate).strip()
        if candidate and not candidate[0].isdigit() and "street" not in candidate.lower():
            if result.city is None:
                result.city = candidate


def _extract_province(result: ParsedAddress, parts: list[str]) -> None:
    if len(parts) >= 3:
        last = parts[-1].strip()
        last = re.sub(r"\d{4}", "", last).strip()
        if last and not last[0].isdigit():
            result.province = last


def _extract_street(result: ParsedAddress, parts: list[str]) -> None:
    if parts:
        first = parts[0].strip()
        has_number = bool(re.match(r"\d", first))
        has_street_word = any(
            w in first.lower()
            for w in ["street", "avenue", "road", "drive", "boulevard", "st.", "ave.", "blvd."]
        )
        if has_number or has_street_word:
            result.street = first


def _try_barangay_fallback(result: ParsedAddress, parts: list[str]) -> None:
    """If no explicit 'Brgy.' marker, try matching the first part as a barangay name."""
    candidate = parts[0].strip()
    candidate = re.sub(r"\s*\d{4}\s*$", "", candidate).strip()
    if not candidate or candidate[0].isdigit():
        return
    if any(w in candidate.lower() for w in ["street", "avenue", "road", "st.", "ave."]):
        return

    try:
        from psgc.search.fuzzy import search
        matches = search(candidate, n=1, match_hooks=["barangay"], threshold=85.0)
        if matches:
            result.barangay = matches[0].place.name
            log.debug("Barangay fallback matched %r -> %s", candidate, result.barangay)
    except (ImportError, KeyError, IndexError):
        log.debug("Barangay fallback failed for %r", candidate)


def _fuzzy_match(result: ParsedAddress) -> None:
    """Try to match parsed components against PSGC data."""
    if not result.barangay and not result.city:
        return

    try:
        from psgc.search.fuzzy import search

        query_parts: list[str] = []
        if result.barangay:
            query_parts.append(result.barangay)
        if result.city:
            query_parts.append(result.city)
        if result.province:
            query_parts.append(result.province)

        query = ", ".join(query_parts)
        matches = search(query, n=1, threshold=50.0)

        if matches:
            match = matches[0]
            result.psgc_match = match
            result.confidence = match.score / 100.0
            place = match.place
            from psgc._loader import get_store
            store = get_store()
            if hasattr(place, "city_code"):
                if not result.city:
                    result.city = store.get_city(place.city_code).name
                if not result.province:
                    result.province = store.get_province(place.province_code).name
                if not result.region:
                    result.region = store.get_region(place.region_code).name
            elif hasattr(place, "province_code"):
                if not result.city:
                    result.city = place.name
                if not result.province:
                    result.province = store.get_province(place.province_code).name
                if not result.region:
                    result.region = store.get_region(place.region_code).name
            elif hasattr(place, "region_code"):
                if not result.province:
                    result.province = place.name
                if not result.region:
                    result.region = store.get_region(place.region_code).name
    except (ImportError, KeyError, IndexError):
        log.debug("Fuzzy match enrichment failed for %r", result.raw)
