"""City/Municipality model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from psgc.models.base import Coordinate, IslandGroup

if TYPE_CHECKING:
    from psgc.models.barangay import Barangay
    from psgc.models.province import Province


@dataclass(slots=True, eq=False)
class City:
    """A Philippine city or municipality."""

    psgc_code: str
    name: str
    province_code: str
    region_code: str
    population: Optional[int] = None
    coordinate: Optional[Coordinate] = None
    island_group: Optional[IslandGroup] = None
    geographic_level: Optional[str] = None
    city_class: Optional[str] = None
    income_classification: Optional[str] = None
    urban_rural: Optional[str] = None

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"City('{self.name}', code='{self.psgc_code}')"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, City) and self.psgc_code == other.psgc_code

    def __hash__(self) -> int:
        return hash(self.psgc_code)

    @property
    def region_prefix(self) -> str:
        return self.psgc_code[:2]

    @property
    def province(self) -> Province:
        from psgc._loader import get_store
        return get_store().get_province(self.province_code)

    @property
    def parent(self) -> Province:
        return self.province

    @property
    def barangays(self) -> list[Barangay]:
        from psgc._loader import get_store
        direct = get_store().barangays_by_city(self.psgc_code)
        if direct:
            return direct
        # Cities with sub-municipalities (e.g. Manila -> Tondo, Sampaloc)
        # have barangays under the sub-muns, not directly under the city.
        all_bgys: list[Barangay] = []
        for sm in self.sub_municipalities:
            all_bgys.extend(get_store().barangays_by_city(sm.psgc_code))
        return all_bgys

    @property
    def children(self) -> list[Barangay]:
        return self.barangays

    @property
    def sub_municipalities(self) -> list[City]:
        """Sub-municipalities under this city (e.g. Manila's Tondo, Sampaloc)."""
        if self.geographic_level == "SubMun":
            return []
        from psgc._loader import get_store
        prefix = self.psgc_code[:5]
        return [c for c in get_store().cities
                if c.geographic_level == "SubMun"
                and c.psgc_code[:5] == prefix
                and c.psgc_code != self.psgc_code]

    @property
    def siblings(self) -> list[City]:
        from psgc._loader import get_store
        return [
            c for c in get_store().cities_by_province(self.province_code)
            if c.psgc_code != self.psgc_code
        ]

    @property
    def is_city(self) -> bool:
        return self.geographic_level == "City"

    @property
    def is_municipality(self) -> bool:
        return self.geographic_level == "Mun"

    @property
    def is_huc(self) -> bool:
        return self.city_class == "Highly Urbanized City"

    @property
    def breadcrumb(self) -> list[str]:
        return [*self.province.breadcrumb, self.name]

    def to_dict(self) -> dict:
        d: dict = {
            "psgc_code": self.psgc_code, "name": self.name,
            "province_code": self.province_code, "region_code": self.region_code,
        }
        if self.population is not None:
            d["population"] = self.population
        if self.coordinate is not None:
            d["coordinate"] = self.coordinate.to_dict()
        if self.island_group is not None:
            d["island_group"] = self.island_group.value
        if self.geographic_level is not None:
            d["geographic_level"] = self.geographic_level
        if self.city_class is not None:
            d["city_class"] = self.city_class
        if self.income_classification is not None:
            d["income_classification"] = self.income_classification
        return d
