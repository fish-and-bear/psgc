"""psgc -- Philippine Standard Geographic Code with coordinates and spatial queries.

Community-maintained. Not affiliated with the Philippine Statistics Authority (PSA).

Quick Start::

    >>> import psgc
    >>> psgc.get("Ermita").coordinate
    Coordinate(14.5833, 120.9822)

    >>> results = psgc.search("Cebu")
    >>> results[0].place.name
    'Cebu'

    >>> psgc.distance("Ermita, Manila", "Cebu City")
    571.0

    >>> len(psgc.regions)
    17
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Union as _Union

from psgc.config import PSGC_DATA_DATE, PSGC_VERSION, setup_logging

__version__: str = PSGC_VERSION
__data_date__: str = PSGC_DATA_DATE


class AmbiguousLookupError(LookupError):
    """Raised when get() matches multiple places with equal confidence.

    The .matches attribute contains the list of matching place objects
    so you can programmatically choose the right one.
    """

    def __init__(self, message: str, matches: list | None = None):
        super().__init__(message)
        self.matches: list = matches or []


if TYPE_CHECKING:
    from psgc.models.barangay import Barangay
    from psgc.models.city import City
    from psgc.models.extended import AdminDivExtended
    from psgc.models.flat import AdminDivFlat
    from psgc.models.province import Province
    from psgc.models.region import Region

    regions: list[Region]
    provinces: list[Province]
    cities: list[City]
    barangays: list[Barangay]
    flat: list[AdminDivFlat]
    tree: list[AdminDivExtended]


def __getattr__(name: str):
    if name in ("regions", "provinces", "cities", "barangays"):
        from psgc._loader import get_store
        return getattr(get_store(), name)

    if name == "flat":
        from psgc._loader import get_store
        return get_store().build_flat()

    if name == "tree":
        from psgc._loader import get_store
        return get_store().build_tree()

    raise AttributeError(f"module 'psgc' has no attribute {name!r}")


from psgc.search.fuzzy import search as search
from psgc.search.autocomplete import suggest as suggest
from psgc.geo.reverse import reverse_geocode as reverse_geocode
from psgc.address.parser import parse_address as parse_address
from psgc.address.formatter import format_address as format_address
from psgc.address.normalizer import sanitize_input as sanitize_input
from psgc.address.validator import validate as validate
from psgc.export.geojson import to_geojson as to_geojson
from psgc.export.formats import to_csv as to_csv
from psgc.export.formats import to_json as to_json

from psgc.results import GeocodeResult, NearestResult, SearchResult


def get(query: str) -> _Union["Region", "Province", "City", "Barangay"]:
    """Look up a place by name or PSGC code.

    Raises LookupError if no confident match is found (score >= 80).
    Raises AmbiguousLookupError if multiple places match with the same
    top score -- disambiguate by adding the city/province name:

        psgc.get("Barangay 1 (Poblacion), Legazpi City")

    >>> psgc.get("Ermita")
    Barangay('Ermita', code='1339501004')

    >>> psgc.get("1339501004")
    Barangay('Ermita', code='1339501004')
    """
    if not isinstance(query, str):
        raise TypeError(f"get() requires a string, got {type(query).__name__}")

    query = query.strip()
    if not query:
        raise LookupError("Empty query")

    from psgc._loader import get_store
    store = get_store()

    if query.isdigit() and len(query) == 10:
        for getter in (store.get_barangay, store.get_city, store.get_region, store.get_province):
            try:
                return getter(query)
            except KeyError:
                continue

    results = search(query, n=10, threshold=80.0)
    if not results:
        raise LookupError(f"No match found for {query!r}")

    query_lower = query.lower().strip()
    _LEVEL_RANK = {"region": 0, "province": 1, "city": 2, "barangay": 3}

    # If the top result is a barangay but a city/province closely matches
    # the "City of <query>" pattern, prefer the higher-level match.
    # This handles cases like get("Taguig") -> "City of Taguig" over "Taguing"
    top = results[0]
    if top.level == "barangay":
        for r in results[1:]:
            if r.score < top.score - 10:
                break
            name_lower = r.place.name.lower()
            if r.level in ("city", "province", "region") and (
                name_lower == f"city of {query_lower}"
                or name_lower == f"{query_lower} city"
                or query_lower == name_lower
            ):
                return r.place

    top_score = results[0].score
    ties = [r for r in results if r.score == top_score]

    if len(ties) == 1:
        return ties[0].place

    def _tiebreak_key(r: SearchResult) -> tuple:
        name_lower = r.place.name.lower()
        exact = name_lower == query_lower
        city_of_match = (name_lower == f"city of {query_lower}"
                         or name_lower == f"{query_lower} city"
                         or f"city of {query_lower}" in name_lower)
        contains = query_lower in name_lower
        level_rank = _LEVEL_RANK.get(r.level, 99)
        return (not exact and not city_of_match, not contains, level_rank)

    ties.sort(key=_tiebreak_key)
    best = ties[0]
    runner_up = ties[1] if len(ties) > 1 else None

    if runner_up and _tiebreak_key(best) == _tiebreak_key(runner_up):
        truly_ambiguous = [r for r in ties if _tiebreak_key(r) == _tiebreak_key(best)]
        names: list[str] = []
        for r in truly_ambiguous:
            place = r.place
            if hasattr(place, "city_code") or hasattr(place, "province_code"):
                names.append(f"  {place.name} in {place.parent.name} ({r.psgc_code})")
            else:
                names.append(f"  {place.name} ({r.psgc_code})")

        hint_place = truly_ambiguous[0].place
        hint = (f'"{hint_place.name}, {hint_place.parent.name}"'
                if hasattr(hint_place, "city_code") else f'"{hint_place.name}"')

        raise AmbiguousLookupError(
            f"{len(truly_ambiguous)} places match {query!r} with equal confidence. "
            f"Disambiguate with the parent name, e.g. psgc.get({hint}):\n" + "\n".join(names),
            matches=[r.place for r in truly_ambiguous],
        )

    return best.place


def exists(query: str) -> bool:
    """Check if a place with this exact name exists in the dataset.

    Uses strict matching (score >= 95) to avoid false positives.
    For fuzzy matching, use search() with a custom threshold.

    >>> psgc.exists("Ermita")
    True
    >>> psgc.exists("Xanadu")
    False
    """
    results = search(query, n=1, threshold=95.0)
    return len(results) > 0


def nearest(latitude: float, longitude: float, n: int = 5) -> list[NearestResult]:
    """Find N nearest barangays to a point. Requires psgc[geo].

    Uses approximate centroids -- results indicate geographic proximity
    but may not reflect exact distances. Distances are straight-line (Haversine).

    >>> results = psgc.nearest(14.5995, 120.9842)
    >>> results[0].place.name
    'Quiapo'
    """
    from psgc.geo.spatial import get_spatial_index
    return get_spatial_index().nearest(float(latitude), float(longitude), n)


def within_radius(latitude: float, longitude: float, radius_km: float) -> list[NearestResult]:
    """Find all barangays within a radius (km). Requires psgc[geo].

    >>> results = psgc.within_radius(14.5995, 120.9842, radius_km=2)
    >>> len(results)
    10
    """
    from psgc.geo.spatial import get_spatial_index
    return get_spatial_index().within_radius(float(latitude), float(longitude), float(radius_km))


def distance(place_a: str, place_b: str) -> float:
    """Straight-line (as-the-crow-flies) distance in km between two places.

    This is NOT driving distance. It uses the Haversine formula to compute
    the great-circle distance over the Earth's surface. Actual road distance
    will be longer. For driving/walking distance, use a routing API like
    OSRM, Google Maps, or Valhalla.

    >>> psgc.distance("City of Mandaluyong", "City of Makati")
    3.2
    """
    from psgc.geo.distance import haversine

    a = get(place_a)
    b = get(place_b)

    if a.coordinate is None:
        raise ValueError(f"No coordinates for {a.name}")
    if b.coordinate is None:
        raise ValueError(f"No coordinates for {b.name}")

    return round(haversine(
        a.coordinate.latitude, a.coordinate.longitude,
        b.coordinate.latitude, b.coordinate.longitude,
    ), 3)


def zip_lookup(zip_code: str) -> dict | None:
    """Look up a ZIP code."""
    from psgc._loader import get_store
    return get_store().lookup_zip(zip_code)


def to_yaml(
    level: str | None = None,
    region: str | None = None,
    province: str | None = None,
    island_group: str | None = None,
    output: str | None = None,
) -> str:
    """Export data as YAML. Requires pyyaml."""
    from psgc.export.formats import to_yaml as _to_yaml
    return _to_yaml(level=level, region=region, province=province,
                    island_group=island_group, output=output)


__all__ = [
    "__version__",
    "__data_date__",
    "setup_logging",
    "regions",
    "provinces",
    "cities",
    "barangays",
    "flat",
    "tree",
    "get",
    "exists",
    "search",
    "suggest",
    "nearest",
    "within_radius",
    "reverse_geocode",
    "distance",
    "parse_address",
    "format_address",
    "validate",
    "to_geojson",
    "to_csv",
    "to_json",
    "to_yaml",
    "sanitize_input",
    "zip_lookup",
    "AmbiguousLookupError",
    "SearchResult",
    "NearestResult",
    "GeocodeResult",
]
