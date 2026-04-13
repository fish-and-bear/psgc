"""Parse PSGC shapefiles and extract centroid coordinates.

Requires: geopandas, shapely
Source: https://github.com/altcoder/philippines-psgc-shapefiles

Usage:
    python -m parsers.parse_shapefiles --shapefile-dir /path/to/shapefiles --output psgc/data/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def extract_centroids(shapefile_dir: str, output_dir: str) -> None:
    """Extract centroids from barangay shapefiles."""
    try:
        import geopandas as gpd
    except ImportError:
        print("geopandas required: pip install psgc[dev]")
        sys.exit(1)

    shp_dir = Path(shapefile_dir)
    out = Path(output_dir)

    barangay_shp = _find_shapefile(shp_dir, "barangay")
    if barangay_shp is None:
        print(f"No barangay shapefile found in {shp_dir}")
        sys.exit(1)

    print(f"Reading shapefile: {barangay_shp}")
    gdf = gpd.read_file(barangay_shp)

    code_col = _detect_code_column(gdf)
    if code_col is None:
        print("Could not detect PSGC code column")
        sys.exit(1)

    print(f"Using code column: {code_col}")
    print(f"Total features: {len(gdf)}")

    centroids: dict[str, dict] = {}
    for _, row in gdf.iterrows():
        code = str(row[code_col]).strip()
        centroid = row.geometry.centroid
        area_km2 = _compute_area_km2(row.geometry)
        centroids[code] = {
            "latitude": round(centroid.y, 6),
            "longitude": round(centroid.x, 6),
            "area_km2": round(area_km2, 2),
        }

    spatial_dir = out / "spatial"
    spatial_dir.mkdir(parents=True, exist_ok=True)
    centroids_path = spatial_dir / "centroids.json"
    with open(centroids_path, "w", encoding="utf-8") as f:
        json.dump(centroids, f, indent=2)
    print(f"Wrote {len(centroids)} centroids to {centroids_path}")


def _find_shapefile(directory: Path, keyword: str) -> Path | None:
    """Find a shapefile matching a keyword."""
    for shp in directory.rglob("*.shp"):
        if keyword.lower() in shp.stem.lower():
            return shp
    shps = list(directory.rglob("*.shp"))
    return shps[0] if shps else None


def _detect_code_column(gdf) -> str | None:
    """Detect the PSGC code column in the GeoDataFrame."""
    candidates = ["PSGC", "psgc_code", "ADM4_PCODE", "ADM3_PCODE", "GEOCODE", "CODE"]
    for col in candidates:
        if col in gdf.columns:
            return col
    for col in gdf.columns:
        if "psgc" in col.lower() or "code" in col.lower():
            return col
    return None


def _compute_area_km2(geometry) -> float:
    """Compute approximate area in km2 from WGS84 geometry."""
    try:
        import pyproj
        from shapely.ops import transform

        project = pyproj.Transformer.from_crs(
            "EPSG:4326", "EPSG:32651", always_xy=True
        ).transform
        projected = transform(project, geometry)
        return projected.area / 1_000_000
    except (ImportError, Exception):
        return geometry.area * 12321  # rough deg2 to km2 at PH latitude


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract centroids from PSGC shapefiles")
    parser.add_argument("--shapefile-dir", required=True, help="Directory with shapefiles")
    parser.add_argument("--output", default="psgc/data", help="Output directory")
    args = parser.parse_args()
    extract_centroids(args.shapefile_dir, args.output)
