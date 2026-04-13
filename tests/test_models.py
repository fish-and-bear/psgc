"""Tests for Pydantic models."""

from __future__ import annotations

from psgc.models.base import AdminLevel, Coordinate, IslandGroup
from psgc.models.barangay import Barangay
from psgc.models.city import City
from psgc.models.flat import AdminDivFlat
from psgc.models.province import Province
from psgc.models.region import Region


class TestCoordinate:
    def test_basic(self):
        c = Coordinate(latitude=14.5995, longitude=120.9842)
        assert c.latitude == 14.5995
        assert c.longitude == 120.9842

    def test_as_tuple(self):
        c = Coordinate(latitude=14.5995, longitude=120.9842)
        assert c.as_tuple() == (14.5995, 120.9842)

    def test_repr(self):
        c = Coordinate(latitude=14.5995, longitude=120.9842)
        assert "14.5995" in repr(c)


class TestRegion:
    def test_load_regions(self):
        from psgc._loader import get_store
        regions = get_store().regions
        assert len(regions) > 0
        assert all(isinstance(r, Region) for r in regions)

    def test_region_has_island_group(self):
        from psgc._loader import get_store
        for r in get_store().regions:
            assert r.island_group is not None

    def test_region_provinces(self):
        from psgc._loader import get_store
        ncr = None
        for r in get_store().regions:
            if "NCR" in r.name:
                ncr = r
                break
        assert ncr is not None
        provinces = ncr.provinces
        assert len(provinces) > 0

    def test_breadcrumb(self):
        from psgc._loader import get_store
        r = get_store().regions[0]
        assert r.breadcrumb == [r.name]


class TestProvince:
    def test_parent_region(self):
        from psgc._loader import get_store
        p = get_store().provinces[0]
        assert p.parent is not None
        assert isinstance(p.parent, Region)

    def test_siblings(self):
        from psgc._loader import get_store
        p = get_store().provinces[0]
        siblings = p.siblings
        assert all(s.psgc_code != p.psgc_code for s in siblings)


class TestCity:
    def test_is_city_or_municipality_or_submun(self):
        from psgc._loader import get_store
        for c in get_store().cities:
            assert c.is_city or c.is_municipality or c.geographic_level == "SubMun"

    def test_parent_province(self):
        from psgc._loader import get_store
        c = get_store().cities[0]
        assert c.parent is not None
        assert isinstance(c.parent, Province)


class TestBarangay:
    def test_population_density(self):
        from psgc._loader import get_store
        for b in get_store().barangays:
            if b.population and b.area_km2:
                assert b.population_density is not None
                assert b.population_density > 0

    def test_urban_rural(self):
        from psgc._loader import get_store
        brgys = get_store().barangays
        has_urban = any(b.is_urban for b in brgys)
        has_rural = any(b.is_rural for b in brgys)
        has_any = any(b.urban_rural is not None for b in brgys)
        if has_any:
            assert has_urban or has_rural

    def test_breadcrumb_length(self):
        from psgc._loader import get_store
        b = get_store().barangays[0]
        assert len(b.breadcrumb) >= 3  # at least region, city, barangay (NCR skips province)

    def test_coordinate(self):
        from psgc._loader import get_store
        b = get_store().barangays[0]
        assert b.coordinate is not None
        assert 4.0 <= b.coordinate.latitude <= 21.0  # PH lat range
        assert 116.0 <= b.coordinate.longitude <= 127.0  # PH lon range


class TestFlat:
    def test_build_flat(self):
        from psgc._loader import get_store
        flat = get_store().build_flat()
        assert len(flat) > 0
        assert all(isinstance(f, AdminDivFlat) for f in flat)

    def test_flat_has_all_levels(self):
        from psgc._loader import get_store
        flat = get_store().build_flat()
        levels = {f.level for f in flat}
        assert AdminLevel.REGION in levels
        assert AdminLevel.PROVINCE in levels
        assert AdminLevel.BARANGAY in levels


class TestExtended:
    def test_build_tree(self):
        from psgc._loader import get_store
        trees = get_store().build_tree()
        assert len(trees) > 0
        assert trees[0].level == AdminLevel.REGION

    def test_tree_depth(self):
        from psgc._loader import get_store
        trees = get_store().build_tree()
        for tree in trees:
            if tree.components:
                province = tree.components[0]
                assert province.level == AdminLevel.PROVINCE
                if province.components:
                    city = province.components[0]
                    assert city.level in (AdminLevel.CITY, AdminLevel.MUNICIPALITY)

    def test_find(self):
        from psgc._loader import get_store
        trees = get_store().build_tree()
        for tree in trees:
            result = tree.find(tree.name)
            assert result is not None
            assert result.name == tree.name

    def test_flatten(self):
        from psgc._loader import get_store
        trees = get_store().build_tree()
        for tree in trees:
            flat = tree.flatten()
            assert len(flat) >= 1
            assert flat[0].name == tree.name
