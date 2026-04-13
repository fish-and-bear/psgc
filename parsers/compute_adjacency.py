"""Compute barangay adjacency from shared polygon edges.

Usage:
    python -m parsers.compute_adjacency --shapefile-dir /path/to/shapefiles --output psgc/data/spatial/adjacency.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def compute_adjacency(shapefile_dir: str, output_path: str) -> None:
    """Build adjacency map from shared polygon boundaries."""
    try:
        import geopandas as gpd
        from shapely.strtree import STRtree
    except ImportError:
        print("geopandas and shapely required: pip install psgc[dev]")
        sys.exit(1)

    shp_dir = Path(shapefile_dir)
    shp_file = None
    for f in shp_dir.rglob("*.shp"):
        if "barangay" in f.stem.lower():
            shp_file = f
            break
    if shp_file is None:
        shps = list(shp_dir.rglob("*.shp"))
        shp_file = shps[0] if shps else None

    if shp_file is None:
        print("No shapefile found")
        sys.exit(1)

    print(f"Reading: {shp_file}")
    gdf = gpd.read_file(shp_file)

    code_col = None
    for col in ["PSGC", "psgc_code", "ADM4_PCODE", "GEOCODE", "CODE"]:
        if col in gdf.columns:
            code_col = col
            break
    if code_col is None:
        for col in gdf.columns:
            if "code" in col.lower():
                code_col = col
                break

    if code_col is None:
        print("Cannot find code column")
        sys.exit(1)

    print(f"Using code column: {code_col}, {len(gdf)} features")

    codes = gdf[code_col].astype(str).tolist()
    geometries = gdf.geometry.tolist()

    tree = STRtree(geometries)
    adjacency: dict[str, list[str]] = defaultdict(list)

    for i, geom in enumerate(geometries):
        candidates = tree.query(geom)
        for j in candidates:
            if i == j:
                continue
            if geom.touches(geometries[j]) or geom.intersects(geometries[j]):
                code_i = codes[i]
                code_j = codes[j]
                if code_j not in adjacency[code_i]:
                    adjacency[code_i].append(code_j)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(dict(adjacency), f, indent=2)

    total_edges = sum(len(v) for v in adjacency.values()) // 2
    print(f"Computed {total_edges} adjacency edges for {len(adjacency)} barangays")
    print(f"Wrote: {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute barangay adjacency")
    parser.add_argument("--shapefile-dir", required=True)
    parser.add_argument("--output", default="psgc/data/spatial/adjacency.json")
    args = parser.parse_args()
    compute_adjacency(args.shapefile_dir, args.output)
