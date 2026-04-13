# psgc

Philippine Standard Geographic Code (PSGC) Python package with **latitude/longitude coordinates**, **spatial queries**, **fuzzy search**, **reverse geocoding**, **address parsing**, and **GeoJSON export**.

42,011 barangays, 1,656 cities, 83 provinces, 18 regions with 2024 Census population data. Based on the official **PSA PSGC Q4 2025 Publication Datafile**.

---

## Quick Start

```bash
pip install psgc
```

```python
import psgc

place = psgc.get("Ermita")
place.coordinate   # Coordinate(14.5833, 120.9822)
place.parent       # City('City of Manila', ...)
place.zip_code     # '1000'
place.breadcrumb   # ['NCR', 'NCR First District', 'City of Manila', 'Ermita']
```

**Requirements:** Python 3.10+

---

## Features

| Feature | Description |
|---|---|
| **Coordinates** | Lat/lng for all ~42,000 barangays, cities, provinces, and regions |
| **`get()`** | Look up any place by name or PSGC code |
| **Fuzzy Search** | RapidFuzz-based matching with Filipino phonetic rules |
| **Spatial Queries** | Nearest barangay, radius search, distance by place name |
| **Reverse Geocoding** | Coordinates to barangay (point-in-polygon + centroid fallback) |
| **Address Parsing** | Parse unstructured Filipino addresses into components |
| **Autocomplete** | Prefix trie for sub-millisecond suggestions |
| **GeoJSON Export** | Export points and boundaries as GeoJSON FeatureCollections |
| **Island Groups** | Every unit tagged Luzon / Visayas / Mindanao |
| **ZIP Codes** | Bidirectional ZIP code to location mapping |
| **Hierarchical Navigation** | `.parent`, `.children`, `.siblings`, `.breadcrumb` |
| **Population Density** | Computed from population and polygon area |
| **CLI** | Full command-line interface for all features |
| **Lightweight** | 1 core dependency (rapidfuzz). stdlib dataclasses, no pydantic. |
| **Typed** | PEP 561 `py.typed`, full IDE autocomplete support |

---

## Installation

```bash
# Core package (search, data, address parsing)
pip install psgc

# With spatial queries (nearest, radius, reverse geocode)
pip install psgc[geo]

# With CLI
pip install psgc[cli]

# Everything
pip install psgc[all]
```

### Optional Extras

| Extra | Adds | Use Case |
|---|---|---|
| `[geo]` | `scipy` | Spatial index, nearest/radius queries |
| `[cli]` | `click` | Command-line interface |
| `[yaml]` | `pyyaml` | YAML export format |
| `[all]` | All of the above | Full install |

---

## Python API

### Look Up a Place

```python
import psgc

# By name (fuzzy matched)
place = psgc.get("Ermita")
place.name          # 'Ermita'
place.coordinate    # Coordinate(14.5833, 120.9822)
place.parent        # City('City of Manila', ...)
place.zip_code      # '1000'
place.is_urban      # True
place.breadcrumb    # ['NCR', ..., 'City of Manila', 'Ermita']

# By PSGC code (instant O(1) lookup)
place = psgc.get("1339501004")

# Check if a place exists
psgc.exists("Ermita")      # True
psgc.exists("Xanadu")      # False

# Ambiguous names raise with helpful guidance
try:
    psgc.get("Barangay 1 (Poblacion)")
except psgc.AmbiguousLookupError as e:
    print(e.matches)  # list of matching places to choose from
    # Disambiguate:
    psgc.get("Barangay 1 (Poblacion), Legazpi City")
```

### Fuzzy Search

```python
results = psgc.search("Cebu")

results[0].name     # 'Cebu'
results[0].score    # 100.0
results[0].level    # 'province'
results[0].place    # Province('Cebu', ...) -- the actual object

# From the result, navigate the hierarchy
results[0].place.children   # list of cities in Cebu

# Custom search with hooks and threshold
results = psgc.search(
    "Sebu",
    n=5,
    match_hooks=["city"],     # search cities only
    threshold=70.0,
    phonetic=True,            # Filipino phonetic matching
)
```

### Autocomplete

```python
results = psgc.suggest("mak", limit=5)
# [{"name": "Makati City", "psgc_code": "...", "level": "city"}, ...]
```

### Spatial Queries

Requires `pip install psgc[geo]`.

```python
# Nearest barangays to a GPS point
results = psgc.nearest(14.5995, 120.9842, n=5)
results[0].place        # Barangay('Quiapo', ...)
results[0].distance_km  # 0.06

# All barangays within 5 km
results = psgc.within_radius(14.5995, 120.9842, radius_km=5)

# Straight-line distance between two places (not driving distance)
psgc.distance("Ermita, Manila", "Cebu City")  # 569.649 km (as the crow flies)

# Reverse geocode: coordinates -> barangay
result = psgc.reverse_geocode(14.5547, 121.0244)
result.barangay   # 'Poblacion'
result.city       # 'Makati City'
result.province   # 'NCR, Third District'
result.place      # Barangay('Poblacion', ...) -- full object
```

### Data Access

```python
# All 17 regions
for r in psgc.regions:
    print(f"{r.name} ({r.island_group.value})")
    print(f"  Lat: {r.coordinate.latitude}, Lng: {r.coordinate.longitude}")

# Hierarchical navigation
brgy = psgc.barangays[0]
brgy.parent                    # parent City
brgy.parent.parent             # parent Province
brgy.parent.parent.parent      # parent Region
brgy.siblings[:3]              # other barangays in same city
brgy.is_urban                  # True/False

# Cities with sub-municipalities (e.g. Manila)
manila = psgc.get("Manila")
manila.children                # 897 barangays (walks through sub-municipalities)
manila.sub_municipalities      # [Tondo I/II, Binondo, Sampaloc, ...]

# Flat denormalized list (ideal for filtering)
urban_ncr = [b for b in psgc.flat if b.region_name and "NCR" in b.region_name and b.urban_rural == "U"]

# Recursive tree
for region_node in psgc.tree:
    for province_node in region_node.components:
        print(f"  {province_node.name}: {len(province_node.components)} cities")
```

### Address Parsing

```python
result = psgc.parse_address("123 Rizal St., Brgy. San Antonio, Makati City")
result.street       # '123 Rizal St.'
result.barangay     # 'San Antonio'
result.city         # 'Makati City'
result.province     # 'NCR, Third District'
result.confidence   # 0.95
```

### ZIP Code Lookup

```python
info = psgc.zip_lookup("1000")
info["area"]      # 'Ermita, Manila'
info["city"]      # 'City of Manila'
```

### PSGC Code Validation

```python
is_valid, reason = psgc.validate("1339501004")
# (True, "Valid barangay code")
```

### Export

```python
# GeoJSON with coordinates
geojson = psgc.to_geojson(level="barangay", region="NCR", as_dict=True)

# CSV with lat/lng columns
psgc.to_csv(level="barangay", output="barangays.csv")
```

### Logging

```python
# Silent by default. Enable for debugging:
# Enable verbose output:
psgc.setup_logging(verbose=True)

# Or via environment variable:
# PSGC_VERBOSE=true python my_script.py
```

---

## CLI

Requires `pip install psgc[cli]`.

```bash
# Look up
psgc search "Cebu" -n 3
psgc suggest "makat"

# Spatial (requires psgc[geo])
psgc nearest 14.5995 120.9842 -n 5
psgc within-radius 14.5995 120.9842 --km 10
psgc reverse-geocode 14.5833 120.9822
psgc distance "Ermita, Manila" "Cebu City"

# Address parsing
psgc parse "Brgy. San Antonio, Makati City"

# Export
psgc export --format geojson --level barangay --region "NCR" -o ncr.geojson
psgc export --format csv --level city -o cities.csv

# Info
psgc info stats
psgc info version
psgc validate 1339501004
psgc zip 1000
```

---

## Data Sources

| Data | Source | Coverage |
|---|---|---|
| **Names, codes, hierarchy** | PSA PSGC Q4 2025 Publication Datafile | All 42,011 barangays |
| **Population** | 2024 Census (via PSGC masterlist) | 99.97% of barangays |
| **Urban/Rural** | PSGC masterlist | 100% |
| **Income classification** | PSGC masterlist | 99% of cities |
| **Coordinates** | HDX/OCHA Nov 2023 shapefiles (polygon centroids) | 87% (36,763 barangays) |
| **Area (km2)** | HDX/OCHA Nov 2023 shapefiles | 87% (36,762 barangays) |

**Coordinates**: 36,763 barangays have real centroids computed from the [HDX Philippines administrative boundary shapefiles](https://data.humdata.org/dataset/cod-ab-phl) (sourced from PSA/NAMRIA, November 2023). The remaining 5,248 barangays have approximate coordinates inherited from their parent city. These are barangays whose PSGC codes changed between the 2023 shapefile release and the Q4 2025 masterlist. As of April 2026, no newer shapefiles have been published by NAMRIA.

---

## Performance

| Operation | Time (42K barangays) |
|---|---|
| `import psgc` | < 1ms (lazy loading) |
| `get("1380100000")` | ~0.001ms (code lookup) |
| `get("Taguig")` | ~100ms (fuzzy search) |
| `search("Manila")` | ~100ms |
| `suggest("mak")` | ~0.5ms |
| `validate(code)` | ~0.001ms |
| `nearest(lat, lng)` | < 1ms (after first call builds index) |

---

## Known Limitations

| What | Limitation | Details |
|---|---|---|
| **Coordinates** | 87% real centroids, 13% approximate | 36,763 from 2023 HDX shapefiles. 5,248 newer barangays use parent city centroid. No 2024/2025 shapefiles exist yet (NAMRIA has not released updated boundaries). |
| **Distance** | Straight-line (Haversine), not driving/walking | Use a routing API (OSRM, Google Maps) for road distance |
| **Reverse geocode** | Uses nearest centroid, not polygon containment | Accurate for 87% of barangays with real centroids |
| **ZIP codes** | Not included | Merge with PHLPost ZIP code data |
| **Area (km2)** | Available for 87% of barangays | `population_density` works for barangays that have shapefile-derived area |
| **City names** | PSA uses "City of X" format | `get("Makati")` auto-resolves to "City of Makati" for major cities. For obscure cities, use the full PSA name or PSGC code. |

---

## Disclaimer

This is a **community-maintained** open-source project. It is **not affiliated with, endorsed by, or officially connected to** the Philippine Statistics Authority (PSA) or NAMRIA.

## Data Attribution

- **PSGC data** (names, codes, population, classifications): [Philippine Statistics Authority](https://psa.gov.ph/classification/psgc). Public information under the Philippine Statistical Act of 2013 (RA 10625).
- **Administrative boundary coordinates and area**: [OCHA HDX Philippines Subnational Administrative Boundaries](https://data.humdata.org/dataset/cod-ab-phl), sourced from PSA and NAMRIA. Licensed under [CC BY-IGO](https://creativecommons.org/licenses/by/3.0/igo/).

## License

[MIT](LICENSE)
