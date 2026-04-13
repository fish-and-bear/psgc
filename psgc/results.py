"""Result types for search, spatial, and geocoding operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union

from psgc.models.barangay import Barangay
from psgc.models.city import City
from psgc.models.province import Province
from psgc.models.region import Region

Place = Union[Region, Province, City, Barangay]


@dataclass(slots=True)
class SearchResult:
    """A single fuzzy search match with the matched geographic object."""

    place: Place
    score: float
    name: str
    level: str

    @property
    def psgc_code(self) -> str:
        return self.place.psgc_code

    @property
    def coordinate(self):
        return self.place.coordinate

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "score": self.score,
            "level": self.level,
            "psgc_code": self.psgc_code,
        }
        if self.coordinate:
            d["latitude"] = self.coordinate.latitude
            d["longitude"] = self.coordinate.longitude
        return d

    def __repr__(self) -> str:
        return f"SearchResult('{self.name}', score={self.score}, level='{self.level}')"


@dataclass(slots=True)
class NearestResult:
    """A nearby place with its straight-line distance from the query point.

    distance_km is the great-circle (Haversine) distance, not driving distance.
    """

    place: Barangay
    distance_km: float

    @property
    def name(self) -> str:
        return self.place.name

    @property
    def psgc_code(self) -> str:
        return self.place.psgc_code

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "psgc_code": self.psgc_code,
            "distance_km": self.distance_km,
            "latitude": self.place.coordinate.latitude if self.place.coordinate else None,
            "longitude": self.place.coordinate.longitude if self.place.coordinate else None,
        }

    def __repr__(self) -> str:
        return f"NearestResult('{self.place.name}', {self.distance_km:.3f} km)"


@dataclass(slots=True)
class GeocodeResult:
    """Result of reverse geocoding a coordinate to a place."""

    place: Barangay
    distance_km: float
    method: str

    @property
    def barangay(self) -> str:
        return self.place.name

    @property
    def city(self) -> str:
        from psgc._loader import get_store
        return get_store().get_city(self.place.city_code).name

    @property
    def province(self) -> str:
        from psgc._loader import get_store
        return get_store().get_province(self.place.province_code).name

    @property
    def region(self) -> str:
        from psgc._loader import get_store
        return get_store().get_region(self.place.region_code).name

    def to_dict(self) -> dict[str, Any]:
        return {
            "barangay": self.barangay,
            "barangay_code": self.place.psgc_code,
            "city": self.city,
            "province": self.province,
            "region": self.region,
            "distance_km": self.distance_km,
            "method": self.method,
            "zip_code": self.place.zip_code,
            "latitude": self.place.coordinate.latitude if self.place.coordinate else None,
            "longitude": self.place.coordinate.longitude if self.place.coordinate else None,
        }

    def __repr__(self) -> str:
        return f"GeocodeResult('{self.barangay}', city='{self.city}', {self.distance_km:.3f} km)"
