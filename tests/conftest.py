"""Shared test fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_store():
    """Reset the data store singleton between tests."""
    import psgc._loader as loader
    loader._store = None
    yield
    loader._store = None


@pytest.fixture
def sample_codes():
    """Return valid PSGC codes from the current dataset (data-independent)."""
    from psgc._loader import get_store
    store = get_store()
    return {
        "region": store.regions[0].psgc_code,
        "province": store.provinces[0].psgc_code,
        "city": store.cities[0].psgc_code,
        "barangay": store.barangays[0].psgc_code,
    }
