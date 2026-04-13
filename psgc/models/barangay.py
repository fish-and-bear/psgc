"""Barangay model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from psgc.models.base import Coordinate, IslandGroup

if TYPE_CHECKING:
    from psgc.models.city import City


@dataclass(slots=True, eq=False)
class Barangay:
    """A Philippine barangay (smallest administrative division)."""

    psgc_code: str
    name: str
    city_code: str
    province_code: str
    region_code: str
    population: Optional[int] = None
    coordinate: Optional[Coordinate] = None
    island_group: Optional[IslandGroup] = None
    urban_rural: Optional[str] = None
    zip_code: Optional[str] = None
    area_km2: Optional[float] = None

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"Barangay('{self.name}', code='{self.psgc_code}')"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Barangay) and self.psgc_code == other.psgc_code

    def __hash__(self) -> int:
        return hash(self.psgc_code)

    @property
    def region_prefix(self) -> str:
        return self.psgc_code[:2]

    @property
    def city(self) -> City:
        from psgc._loader import get_store
        return get_store().get_city(self.city_code)

    @property
    def parent(self) -> City:
        return self.city

    @property
    def siblings(self) -> list[Barangay]:
        from psgc._loader import get_store
        return [
            b for b in get_store().barangays_by_city(self.city_code)
            if b.psgc_code != self.psgc_code
        ]

    @property
    def is_urban(self) -> bool:
        return self.urban_rural == "U"

    @property
    def is_rural(self) -> bool:
        return self.urban_rural == "R"

    @property
    def population_density(self) -> float | None:
        """Population per square kilometer.

        Returns None if area_km2 is not available (requires shapefile data).
        """
        if self.population and self.area_km2 and self.area_km2 > 0:
            return self.population / self.area_km2
        return None

    @property
    def neighbors(self) -> list[Barangay]:
        from psgc._loader import get_store
        return get_store().get_neighbors(self.psgc_code)

    @property
    def breadcrumb(self) -> list[str]:
        return [*self.city.breadcrumb, self.name]

    def to_dict(self) -> dict:
        d: dict = {
            "psgc_code": self.psgc_code, "name": self.name,
            "city_code": self.city_code, "province_code": self.province_code,
            "region_code": self.region_code,
        }
        if self.population is not None:
            d["population"] = self.population
        if self.coordinate is not None:
            d["coordinate"] = self.coordinate.to_dict()
        if self.island_group is not None:
            d["island_group"] = self.island_group.value
        if self.urban_rural is not None:
            d["urban_rural"] = self.urban_rural
        if self.zip_code is not None:
            d["zip_code"] = self.zip_code
        if self.area_km2 is not None:
            d["area_km2"] = self.area_km2
        return d
