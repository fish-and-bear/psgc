"""Lazy data loader with caching and hierarchical navigation."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from psgc.config import config
from psgc.models.barangay import Barangay
from psgc.models.base import AdminLevel, Coordinate, IslandGroup
from psgc.models.city import City
from psgc.models.extended import AdminDivExtended
from psgc.models.flat import AdminDivFlat
from psgc.models.province import Province
from psgc.models.region import Region

log = logging.getLogger(__name__)


def _load_json(path: Path) -> list | dict:
    log.debug("Loading %s", path.name)
    t0 = time.perf_counter()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    elapsed = (time.perf_counter() - t0) * 1000
    count = len(data) if isinstance(data, (list, dict)) else 0
    log.debug("Loaded %s: %d entries in %.1fms", path.name, count, elapsed)
    return data


def _parse_coord(raw: dict | None) -> Coordinate | None:
    if raw is None:
        return None
    try:
        return Coordinate(latitude=raw["latitude"], longitude=raw["longitude"])
    except (KeyError, TypeError):
        log.warning("Malformed coordinate data: %s", raw)
        return None


def _parse_island(raw: str | None) -> IslandGroup | None:
    if raw is None:
        return None
    try:
        return IslandGroup(raw)
    except ValueError:
        log.warning("Unknown island group: %s", raw)
        return None


class DataStore:
    """Central data store with lazy loading and indexed lookups."""

    def __init__(self) -> None:
        self._regions: list[Region] | None = None
        self._provinces: list[Province] | None = None
        self._cities: list[City] | None = None
        self._barangays: list[Barangay] | None = None
        self._zip_codes: dict | None = None
        self._adjacency: dict[str, list[str]] | None = None

        self._region_idx: dict[str, Region] | None = None
        self._province_idx: dict[str, Province] | None = None
        self._city_idx: dict[str, City] | None = None
        self._barangay_idx: dict[str, Barangay] | None = None

        self._provinces_by_region: dict[str, list[Province]] | None = None
        self._cities_by_province: dict[str, list[City]] | None = None
        self._barangays_by_city: dict[str, list[Barangay]] | None = None

        self._flat_cache: list[AdminDivFlat] | None = None
        self._tree_cache: list[AdminDivExtended] | None = None

    def _ensure_regions(self) -> None:
        if self._regions is not None:
            return
        data = _load_json(config.core_data_dir / "regions.json")
        self._regions = [
            Region(
                psgc_code=r["psgc_code"], name=r["name"],
                population=r.get("population"),
                coordinate=_parse_coord(r.get("coordinate")),
                island_group=_parse_island(r.get("island_group")),
            )
            for r in data
        ]
        self._region_idx = {r.psgc_code: r for r in self._regions}
        log.info("Loaded %d regions", len(self._regions))

    def _ensure_provinces(self) -> None:
        if self._provinces is not None:
            return
        data = _load_json(config.core_data_dir / "provinces.json")
        self._provinces = [
            Province(
                psgc_code=p["psgc_code"], name=p["name"],
                region_code=p["region_code"],
                population=p.get("population"),
                coordinate=_parse_coord(p.get("coordinate")),
                island_group=_parse_island(p.get("island_group")),
                income_classification=p.get("income_classification"),
            )
            for p in data
        ]
        self._province_idx = {p.psgc_code: p for p in self._provinces}
        self._provinces_by_region = {}
        for p in self._provinces:
            self._provinces_by_region.setdefault(p.region_code, []).append(p)
        log.info("Loaded %d provinces across %d regions", len(self._provinces), len(self._provinces_by_region))

    def _ensure_cities(self) -> None:
        if self._cities is not None:
            return
        data = _load_json(config.core_data_dir / "cities.json")
        self._cities = [
            City(
                psgc_code=c["psgc_code"], name=c["name"],
                province_code=c["province_code"], region_code=c["region_code"],
                population=c.get("population"),
                coordinate=_parse_coord(c.get("coordinate")),
                island_group=_parse_island(c.get("island_group")),
                geographic_level=c.get("geographic_level"),
                city_class=c.get("city_class"),
                income_classification=c.get("income_classification"),
                urban_rural=c.get("urban_rural"),
            )
            for c in data
        ]
        self._city_idx = {c.psgc_code: c for c in self._cities}
        self._cities_by_province = {}
        for c in self._cities:
            self._cities_by_province.setdefault(c.province_code, []).append(c)
        log.info("Loaded %d cities/municipalities", len(self._cities))

    def _ensure_barangays(self) -> None:
        if self._barangays is not None:
            return
        data = _load_json(config.core_data_dir / "barangays.json")
        self._barangays = [
            Barangay(
                psgc_code=b["psgc_code"], name=b["name"],
                city_code=b["city_code"], province_code=b["province_code"],
                region_code=b["region_code"],
                population=b.get("population"),
                coordinate=_parse_coord(b.get("coordinate")),
                island_group=_parse_island(b.get("island_group")),
                urban_rural=b.get("urban_rural"),
                zip_code=b.get("zip_code"),
                area_km2=b.get("area_km2"),
            )
            for b in data
        ]
        self._barangay_idx = {b.psgc_code: b for b in self._barangays}
        self._barangays_by_city = {}
        for b in self._barangays:
            self._barangays_by_city.setdefault(b.city_code, []).append(b)
        with_coords = sum(1 for b in self._barangays if b.coordinate is not None)
        log.info("Loaded %d barangays (%d with coordinates)", len(self._barangays), with_coords)

    def _ensure_zip_codes(self) -> None:
        if self._zip_codes is not None:
            return
        self._zip_codes = _load_json(config.core_data_dir / "zip_codes.json")
        log.info("Loaded %d ZIP codes", len(self._zip_codes))

    def _ensure_adjacency(self) -> None:
        if self._adjacency is not None:
            return
        adj_path = config.spatial_dir / "adjacency.json"
        if adj_path.exists():
            self._adjacency = _load_json(adj_path)
            log.info("Loaded adjacency data: %d entries", len(self._adjacency))
        else:
            self._adjacency = {}
            log.debug("No adjacency data found at %s", adj_path)

    @property
    def regions(self) -> list[Region]:
        self._ensure_regions()
        return list(self._regions)  # type: ignore

    @property
    def provinces(self) -> list[Province]:
        self._ensure_provinces()
        return list(self._provinces)  # type: ignore

    @property
    def cities(self) -> list[City]:
        self._ensure_cities()
        return list(self._cities)  # type: ignore

    @property
    def barangays(self) -> list[Barangay]:
        self._ensure_barangays()
        return list(self._barangays)  # type: ignore

    @property
    def zip_codes(self) -> dict:
        self._ensure_zip_codes()
        return self._zip_codes  # type: ignore

    def get_region(self, code: str) -> Region:
        self._ensure_regions()
        r = self._region_idx.get(code)  # type: ignore
        if r is None:
            raise KeyError(f"Region not found: {code}")
        return r

    def get_province(self, code: str) -> Province:
        self._ensure_provinces()
        p = self._province_idx.get(code)  # type: ignore
        if p is None:
            log.warning("Province lookup failed: code=%s", code)
            raise KeyError(f"Province not found: {code}")
        return p

    def get_city(self, code: str) -> City:
        self._ensure_cities()
        c = self._city_idx.get(code)  # type: ignore
        if c is None:
            log.warning("City lookup failed: code=%s", code)
            raise KeyError(f"City not found: {code}")
        return c

    def get_barangay(self, code: str) -> Barangay:
        self._ensure_barangays()
        b = self._barangay_idx.get(code)  # type: ignore
        if b is None:
            raise KeyError(f"Barangay not found: {code}")
        return b

    def provinces_by_region(self, region_code: str) -> list[Province]:
        self._ensure_provinces()
        return self._provinces_by_region.get(region_code, [])  # type: ignore

    def cities_by_province(self, province_code: str) -> list[City]:
        self._ensure_cities()
        return self._cities_by_province.get(province_code, [])  # type: ignore

    def barangays_by_city(self, city_code: str) -> list[Barangay]:
        self._ensure_barangays()
        return self._barangays_by_city.get(city_code, [])  # type: ignore

    def get_neighbors(self, psgc_code: str) -> list[Barangay]:
        self._ensure_adjacency()
        self._ensure_barangays()
        neighbor_codes = self._adjacency.get(psgc_code, [])  # type: ignore
        return [
            self._barangay_idx[c]  # type: ignore
            for c in neighbor_codes
            if c in self._barangay_idx  # type: ignore
        ]

    def lookup_zip(self, zip_code: str) -> dict | None:
        self._ensure_zip_codes()
        return self._zip_codes.get(zip_code)  # type: ignore

    def validate_code(self, code: str) -> tuple[bool, str]:
        if not isinstance(code, str):
            return False, f"PSGC code must be a string, got {type(code).__name__}"
        code = code.strip()
        if not code or not code.isdigit():
            return False, "PSGC code must be a numeric string"
        if len(code) != 10:
            return False, f"PSGC code must be 10 digits, got {len(code)}"

        self._ensure_regions()
        self._ensure_provinces()
        self._ensure_cities()
        self._ensure_barangays()

        if code in self._region_idx:  # type: ignore
            return True, "Valid region code"
        if code in self._province_idx:  # type: ignore
            return True, "Valid province code"
        if code in self._city_idx:  # type: ignore
            return True, "Valid city/municipality code"
        if code in self._barangay_idx:  # type: ignore
            return True, "Valid barangay code"

        return False, "Code not found in current PSGC dataset"

    def build_flat(self) -> list[AdminDivFlat]:
        """Build a flat denormalized list (cached after first call)."""
        if self._flat_cache is not None:
            return self._flat_cache

        result: list[AdminDivFlat] = []

        for r in self.regions:
            result.append(AdminDivFlat(
                psgc_code=r.psgc_code, name=r.name, level=AdminLevel.REGION,
                island_group=r.island_group, population=r.population,
                coordinate=r.coordinate, region_code=r.psgc_code,
                region_name=r.name,
            ))

        for p in self.provinces:
            r = self.get_region(p.region_code)
            result.append(AdminDivFlat(
                psgc_code=p.psgc_code, name=p.name, level=AdminLevel.PROVINCE,
                island_group=p.island_group or r.island_group, population=p.population,
                coordinate=p.coordinate, income_classification=p.income_classification,
                region_code=p.region_code, region_name=r.name,
                province_code=p.psgc_code, province_name=p.name,
            ))

        for c in self.cities:
            p = self.get_province(c.province_code)
            r = self.get_region(c.region_code)
            level = AdminLevel.CITY if c.geographic_level == "City" else AdminLevel.MUNICIPALITY
            result.append(AdminDivFlat(
                psgc_code=c.psgc_code, name=c.name, level=level,
                island_group=c.island_group or r.island_group, population=c.population,
                coordinate=c.coordinate, city_class=c.city_class,
                income_classification=c.income_classification,
                region_code=c.region_code, region_name=r.name,
                province_code=c.province_code, province_name=p.name,
                city_code=c.psgc_code, city_name=c.name,
            ))

        for b in self.barangays:
            c = self.get_city(b.city_code)
            p = self.get_province(b.province_code)
            r = self.get_region(b.region_code)
            result.append(AdminDivFlat(
                psgc_code=b.psgc_code, name=b.name, level=AdminLevel.BARANGAY,
                island_group=b.island_group or r.island_group, population=b.population,
                coordinate=b.coordinate, urban_rural=b.urban_rural,
                zip_code=b.zip_code, area_km2=b.area_km2,
                region_code=b.region_code, region_name=r.name,
                province_code=b.province_code, province_name=p.name,
                city_code=b.city_code, city_name=c.name,
            ))

        self._flat_cache = result
        return result

    def build_tree(self) -> list[AdminDivExtended]:
        """Build a recursive tree (cached after first call)."""
        if self._tree_cache is not None:
            return self._tree_cache

        trees: list[AdminDivExtended] = []

        for r in self.regions:
            province_nodes: list[AdminDivExtended] = []
            for p in self.provinces_by_region(r.psgc_code):
                city_nodes: list[AdminDivExtended] = []
                for c in self.cities_by_province(p.psgc_code):
                    brgy_nodes = [
                        AdminDivExtended(
                            psgc_code=b.psgc_code, name=b.name,
                            level=AdminLevel.BARANGAY,
                            island_group=b.island_group,
                            population=b.population, coordinate=b.coordinate,
                            urban_rural=b.urban_rural, zip_code=b.zip_code,
                            area_km2=b.area_km2,
                        )
                        for b in self.barangays_by_city(c.psgc_code)
                    ]
                    level = AdminLevel.CITY if c.geographic_level == "City" else AdminLevel.MUNICIPALITY
                    city_nodes.append(AdminDivExtended(
                        psgc_code=c.psgc_code, name=c.name, level=level,
                        island_group=c.island_group, population=c.population,
                        coordinate=c.coordinate, city_class=c.city_class,
                        income_classification=c.income_classification,
                        components=brgy_nodes,
                    ))
                province_nodes.append(AdminDivExtended(
                    psgc_code=p.psgc_code, name=p.name,
                    level=AdminLevel.PROVINCE,
                    island_group=p.island_group, population=p.population,
                    coordinate=p.coordinate,
                    income_classification=p.income_classification,
                    components=city_nodes,
                ))
            trees.append(AdminDivExtended(
                psgc_code=r.psgc_code, name=r.name, level=AdminLevel.REGION,
                island_group=r.island_group, population=r.population,
                coordinate=r.coordinate, components=province_nodes,
            ))

        self._tree_cache = trees
        return trees


import threading

_store: DataStore | None = None
_store_lock = threading.Lock()


def get_store() -> DataStore:
    """Return the singleton DataStore, creating it on first call."""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = DataStore()
    return _store
