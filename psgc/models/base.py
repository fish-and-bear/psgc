"""Base types and enums for Philippine geographic models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class IslandGroup(str, Enum):
    """Major Philippine island group classification."""
    LUZON = "luzon"
    VISAYAS = "visayas"
    MINDANAO = "mindanao"


class AdminLevel(str, Enum):
    """PSGC administrative level codes."""
    REGION = "Reg"
    PROVINCE = "Prov"
    CITY = "City"
    MUNICIPALITY = "Mun"
    SUB_MUNICIPALITY = "SubMun"
    BARANGAY = "Bgy"


ISLAND_GROUP_BY_REGION: dict[str, IslandGroup] = {
    "01": IslandGroup.LUZON,
    "02": IslandGroup.LUZON,
    "03": IslandGroup.LUZON,
    "04": IslandGroup.LUZON,
    "05": IslandGroup.LUZON,
    "06": IslandGroup.VISAYAS,
    "07": IslandGroup.VISAYAS,
    "08": IslandGroup.VISAYAS,
    "09": IslandGroup.MINDANAO,
    "10": IslandGroup.MINDANAO,
    "11": IslandGroup.MINDANAO,
    "12": IslandGroup.MINDANAO,
    "13": IslandGroup.LUZON,
    "14": IslandGroup.LUZON,
    "16": IslandGroup.MINDANAO,
    "17": IslandGroup.LUZON,
    "18": IslandGroup.VISAYAS,   # NIR (Negros Island Region)
    "19": IslandGroup.MINDANAO,
}


@dataclass(slots=True)
class Coordinate:
    """Geographic coordinate (WGS84).

    Note: Coordinates in the bundled dataset are approximate centroids
    derived from the administrative hierarchy, NOT exact geocoded positions.
    For precise coordinates, run the data pipeline with actual shapefiles.
    """

    latitude: float
    longitude: float

    def as_tuple(self) -> tuple[float, float]:
        return (self.latitude, self.longitude)

    def __repr__(self) -> str:
        return f"Coordinate({self.latitude:.4f}, {self.longitude:.4f})"

    def to_dict(self) -> dict:
        return {"latitude": self.latitude, "longitude": self.longitude}
