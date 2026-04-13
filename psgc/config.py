"""Configuration management via environment variables and module-level attributes."""

from __future__ import annotations

import logging
import os
from pathlib import Path


PSGC_VERSION = "2026.1.13.0"
PSGC_DATA_DATE = "2026-01-13"

_PACKAGE_DIR = Path(__file__).parent
_DATA_DIR = _PACKAGE_DIR / "data"
_CORE_DATA_DIR = _DATA_DIR / "core"
_BOUNDARY_DIR = _DATA_DIR / "boundaries"
_SPATIAL_DIR = _DATA_DIR / "spatial"


def _env_bool(key: str, default: bool = False) -> bool:
    return os.environ.get(key, str(default)).lower() in ("true", "1", "yes")


def setup_logging(verbose: bool = False) -> None:
    """Configure the psgc logger.

    Call this to enable log output. By default the library is silent
    (NullHandler). Setting verbose=True or PSGC_VERBOSE=true adds a
    StreamHandler at DEBUG level.
    """
    logger = logging.getLogger("psgc")
    if verbose and not any(
        isinstance(h, logging.StreamHandler) for h in logger.handlers
    ):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)


class Config:
    """Runtime configuration with environment variable overrides.

    Priority: function parameter > module attribute > env var > default.
    """

    def __init__(self) -> None:
        self.verbose: bool = _env_bool("PSGC_VERBOSE")
        self.cache_dir: Path = Path(
            os.environ.get("PSGC_CACHE_DIR", Path.home() / ".cache" / "psgc")
        )

        # NullHandler = silent unless user opts in
        logging.getLogger("psgc").addHandler(logging.NullHandler())
        if self.verbose:
            setup_logging(verbose=True)

    @property
    def data_dir(self) -> Path:
        return _DATA_DIR

    @property
    def core_data_dir(self) -> Path:
        return _CORE_DATA_DIR

    @property
    def boundary_dir(self) -> Path:
        return _BOUNDARY_DIR

    @property
    def spatial_dir(self) -> Path:
        return _SPATIAL_DIR


config = Config()
