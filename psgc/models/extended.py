"""Extended recursive tree model with rich metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from psgc.models.base import AdminLevel, Coordinate, IslandGroup


@dataclass
class AdminDivExtended:
    """Recursive tree node representing a geographic division."""

    psgc_code: str
    name: str
    level: AdminLevel
    island_group: Optional[IslandGroup] = None
    population: Optional[int] = None
    coordinate: Optional[Coordinate] = None
    income_classification: Optional[str] = None
    city_class: Optional[str] = None
    urban_rural: Optional[str] = None
    zip_code: Optional[str] = None
    area_km2: Optional[float] = None

    components: list[AdminDivExtended] = field(default_factory=list)

    @property
    def is_leaf(self) -> bool:
        return len(self.components) == 0

    @property
    def total_population(self) -> int:
        """Population from the leaf level up (avoids double-counting).

        Leaf nodes return their own population. Non-leaf nodes return
        the sum of their children's total_population, ignoring their
        own .population to prevent double-counting (since parent
        population figures already aggregate their children in the
        PSGC data).
        """
        if self.is_leaf:
            return self.population or 0
        child_sum = sum(c.total_population for c in self.components)
        return child_sum if child_sum > 0 else (self.population or 0)

    def find(self, name: str) -> AdminDivExtended | None:
        lower = name.lower()
        if self.name.lower() == lower:
            return self
        for child in self.components:
            result = child.find(name)
            if result is not None:
                return result
        return None

    def flatten(self) -> list[AdminDivExtended]:
        result = [self]
        for child in self.components:
            result.extend(child.flatten())
        return result
