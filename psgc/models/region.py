"""Region model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from psgc.models.base import Coordinate, IslandGroup

if TYPE_CHECKING:
    from psgc.models.province import Province


@dataclass(slots=True, eq=False)
class Region:
    """A Philippine administrative region."""

    psgc_code: str
    name: str
    population: Optional[int] = None
    coordinate: Optional[Coordinate] = None
    island_group: Optional[IslandGroup] = None

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"Region('{self.name}', code='{self.psgc_code}')"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Region) and self.psgc_code == other.psgc_code

    def __hash__(self) -> int:
        return hash(self.psgc_code)

    @property
    def region_prefix(self) -> str:
        return self.psgc_code[:2]

    @property
    def provinces(self) -> list[Province]:
        from psgc._loader import get_store
        return get_store().provinces_by_region(self.psgc_code)

    @property
    def children(self) -> list[Province]:
        return self.provinces

    @property
    def breadcrumb(self) -> list[str]:
        return [self.name]

    def to_dict(self) -> dict:
        d: dict = {"psgc_code": self.psgc_code, "name": self.name}
        if self.population is not None:
            d["population"] = self.population
        if self.coordinate is not None:
            d["coordinate"] = self.coordinate.to_dict()
        if self.island_group is not None:
            d["island_group"] = self.island_group.value
        return d
