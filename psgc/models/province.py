"""Province model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from psgc.models.base import Coordinate, IslandGroup

if TYPE_CHECKING:
    from psgc.models.city import City
    from psgc.models.region import Region


@dataclass(slots=True, eq=False)
class Province:
    """A Philippine province or NCR district."""

    psgc_code: str
    name: str
    region_code: str
    population: Optional[int] = None
    coordinate: Optional[Coordinate] = None
    island_group: Optional[IslandGroup] = None
    income_classification: Optional[str] = None

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"Province('{self.name}', code='{self.psgc_code}')"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Province) and self.psgc_code == other.psgc_code

    def __hash__(self) -> int:
        return hash(self.psgc_code)

    @property
    def region_prefix(self) -> str:
        return self.psgc_code[:2]

    @property
    def region(self) -> Region:
        from psgc._loader import get_store
        return get_store().get_region(self.region_code)

    @property
    def parent(self) -> Region:
        return self.region

    @property
    def cities(self) -> list[City]:
        from psgc._loader import get_store
        return get_store().cities_by_province(self.psgc_code)

    @property
    def children(self) -> list[City]:
        return self.cities

    @property
    def siblings(self) -> list[Province]:
        from psgc._loader import get_store
        return [
            p for p in get_store().provinces_by_region(self.region_code)
            if p.psgc_code != self.psgc_code
        ]

    @property
    def breadcrumb(self) -> list[str]:
        reg_name = self.region.name
        if reg_name == self.name:
            return [self.name]
        return [reg_name, self.name]

    def to_dict(self) -> dict:
        d: dict = {
            "psgc_code": self.psgc_code, "name": self.name,
            "region_code": self.region_code,
        }
        if self.population is not None:
            d["population"] = self.population
        if self.coordinate is not None:
            d["coordinate"] = self.coordinate.to_dict()
        if self.island_group is not None:
            d["island_group"] = self.island_group.value
        if self.income_classification is not None:
            d["income_classification"] = self.income_classification
        return d
