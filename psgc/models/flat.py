"""Flat (denormalized) model for easy filtering and search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from psgc.models.base import AdminLevel, Coordinate, IslandGroup


@dataclass(slots=True)
class AdminDivFlat:
    """Denormalized geographic unit with all parent info inlined.

    Ideal for filtering, CSV export, and tabular operations.
    """

    psgc_code: str
    name: str
    level: AdminLevel
    island_group: Optional[IslandGroup] = None

    region_code: Optional[str] = None
    region_name: Optional[str] = None
    province_code: Optional[str] = None
    province_name: Optional[str] = None
    city_code: Optional[str] = None
    city_name: Optional[str] = None

    population: Optional[int] = None
    coordinate: Optional[Coordinate] = None
    urban_rural: Optional[str] = None
    income_classification: Optional[str] = None
    city_class: Optional[str] = None
    zip_code: Optional[str] = None
    area_km2: Optional[float] = None

    @property
    def population_density(self) -> float | None:
        if self.population and self.area_km2 and self.area_km2 > 0:
            return self.population / self.area_km2
        return None

    @property
    def breadcrumb(self) -> list[str]:
        parts: list[str] = []
        if self.region_name:
            parts.append(self.region_name)
        if self.province_name:
            parts.append(self.province_name)
        if self.city_name:
            parts.append(self.city_name)
        if self.level == AdminLevel.BARANGAY:
            parts.append(self.name)
        return parts

    def to_dict(self) -> dict:
        d: dict = {
            "psgc_code": self.psgc_code, "name": self.name,
            "level": self.level.value,
        }
        for attr in (
            "island_group", "region_code", "region_name", "province_code",
            "province_name", "city_code", "city_name", "population",
            "urban_rural", "income_classification", "city_class",
            "zip_code", "area_km2",
        ):
            val = getattr(self, attr)
            if val is not None:
                d[attr] = val.value if isinstance(val, IslandGroup) else val
        if self.coordinate is not None:
            d["coordinate"] = self.coordinate.to_dict()
        return d
