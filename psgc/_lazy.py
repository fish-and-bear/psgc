"""Lazy import helpers for optional dependencies."""

from __future__ import annotations

import importlib
from typing import Any


def lazy_import(module_name: str, package: str | None = None) -> Any:
    """Import a module lazily, raising a helpful error if not installed."""
    try:
        return importlib.import_module(module_name, package)
    except ImportError:
        extra = _MODULE_TO_EXTRA.get(module_name, "all")
        raise ImportError(
            f"'{module_name}' is required for this feature. "
            f"Install it with: pip install psgc[{extra}]"
        ) from None


_MODULE_TO_EXTRA: dict[str, str] = {
    "scipy": "geo",
    "scipy.spatial": "geo",
    "geopandas": "dev",
    "shapely": "dev",
    "fiona": "dev",
}
