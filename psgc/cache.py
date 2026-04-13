"""Disk cache for downloaded historical data."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from psgc.config import config

log = logging.getLogger(__name__)


def _cache_dir() -> Path:
    d = config.cache_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_path(key: str) -> Path:
    """Return the filesystem path for a cache key."""
    safe = hashlib.sha256(key.encode()).hexdigest()[:16]
    return _cache_dir() / f"{safe}.json"


def get_cached(key: str) -> dict | list | None:
    """Retrieve cached data by key, or None on miss."""
    p = cache_path(key)
    if p.exists():
        log.debug("Cache hit: %s -> %s", key, p.name)
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    log.debug("Cache miss: %s", key)
    return None


def set_cached(key: str, data: dict | list) -> Path:
    """Write data to the cache. Returns the file path."""
    p = cache_path(key)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    log.debug("Cached %s -> %s", key, p.name)
    return p


def clear_cache() -> int:
    """Remove all cached files. Returns number of files removed."""
    d = _cache_dir()
    if not d.exists():
        return 0
    files = list(d.glob("*.json"))
    for f in files:
        f.unlink()
    log.info("Cleared %d cached files from %s", len(files), d)
    return len(files)


def cache_info() -> dict:
    """Return cache statistics."""
    d = _cache_dir()
    if not d.exists():
        return {"path": str(d), "files": 0, "size_bytes": 0}
    files = list(d.glob("*.json"))
    total_size = sum(f.stat().st_size for f in files)
    return {
        "path": str(d),
        "files": len(files),
        "size_bytes": total_size,
        "size_mb": round(total_size / (1024 * 1024), 2),
    }
