"""Full data pipeline: build all psgc data from source files.

Usage:
    python -m parsers.build_data \\
        --psgc-xlsx PSGC_masterlist.xlsx \\
        --shapefile-dir /path/to/philippines-psgc-shapefiles \\
        --zip-codes zip_codes.sql

This runs all parsers in sequence:
1. Parse PSGC masterlist -> core JSON files
2. Extract centroids from shapefiles
3. Merge centroids into core data
4. Compute adjacency from shapefiles
5. Parse ZIP codes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build all psgc data from sources")
    parser.add_argument("--psgc-xlsx", required=True, help="PSGC masterlist Excel file")
    parser.add_argument("--shapefile-dir", required=True, help="Directory with PSGC shapefiles")
    parser.add_argument("--zip-codes", help="ZIP code SQL dump or CSV file")
    parser.add_argument("--output", default="psgc/data", help="Output data directory")
    args = parser.parse_args()

    output = Path(args.output)
    core_dir = output / "core"
    spatial_dir = output / "spatial"

    print("=" * 60)
    print("PSGC Data Build Pipeline")
    print("=" * 60)

    print("\n[1/5] Parsing PSGC masterlist...")
    from parsers.parse_psgc import parse_masterlist
    parse_masterlist(args.psgc_xlsx, str(core_dir))

    print("\n[2/5] Extracting centroids from shapefiles...")
    from parsers.parse_shapefiles import extract_centroids
    extract_centroids(args.shapefile_dir, str(output))

    print("\n[3/5] Merging centroids into core data...")
    from parsers.compute_centroids import merge_centroids
    merge_centroids(str(spatial_dir / "centroids.json"), str(core_dir))

    print("\n[4/5] Computing adjacency...")
    from parsers.compute_adjacency import compute_adjacency
    compute_adjacency(args.shapefile_dir, str(spatial_dir / "adjacency.json"))

    if args.zip_codes:
        print("\n[5/5] Parsing ZIP codes...")
        from parsers.match_zip_codes import parse_zip_codes
        parse_zip_codes(args.zip_codes, str(core_dir / "zip_codes.json"))
    else:
        print("\n[5/5] Skipping ZIP codes (no file provided)")

    print("\n" + "=" * 60)
    print("Build complete!")
    print(f"Output: {output.resolve()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
