"""Format geographic data into standard Philippine address strings."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psgc.models.barangay import Barangay
    from psgc.models.city import City


def format_address(
    barangay: Barangay | None = None,
    city: City | None = None,
    include_region: bool = False,
    include_zip: bool = True,
) -> str:
    """Format a standardized Philippine address string.

    Args:
        barangay: Barangay model instance
        city: City model instance (used if barangay not provided)
        include_region: Include region name
        include_zip: Include ZIP code

    Returns:
        Formatted address string.
    """
    parts: list[str] = []

    if barangay is not None:
        from psgc._loader import get_store
        store = get_store()

        parts.append(f"Brgy. {barangay.name}")

        c = store.get_city(barangay.city_code)
        parts.append(c.name)

        p = store.get_province(barangay.province_code)
        if p.name != c.name and c.name not in p.name:
            parts.append(p.name)

        if include_region:
            r = store.get_region(barangay.region_code)
            if not any(r.name in existing or existing in r.name for existing in parts):
                parts.append(r.name)

        if include_zip and barangay.zip_code:
            parts[-1] = f"{parts[-1]} {barangay.zip_code}"

    elif city is not None:
        from psgc._loader import get_store
        store = get_store()

        parts.append(city.name)
        p = store.get_province(city.province_code)
        if p.name != city.name and city.name not in p.name:
            parts.append(p.name)

        if include_region:
            r = store.get_region(city.region_code)
            if not any(r.name in existing or existing in r.name for existing in parts):
                parts.append(r.name)

    return ", ".join(parts)
