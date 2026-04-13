"""Tests for address parsing, normalization, and validation."""

from __future__ import annotations


class TestNormalizer:
    def test_expand_abbreviations(self):
        from psgc.address.normalizer import expand_abbreviations
        assert "barangay" in expand_abbreviations("Brgy. Test")
        assert "street" in expand_abbreviations("Rizal St.")

    def test_normalize_name(self):
        from psgc.address.normalizer import normalize_name
        assert normalize_name("City of Manila") == "Manila"
        assert normalize_name("Makati City") == "Makati"

    def test_sanitize_input(self):
        from psgc.address.normalizer import sanitize_input
        result = sanitize_input("  Hello   World  ")
        assert result == "hello world"

    def test_sanitize_with_exclude(self):
        from psgc.address.normalizer import sanitize_input
        result = sanitize_input("City of Manila", exclude=["city of "])
        assert result == "manila"


class TestParser:
    def test_basic_parse(self):
        from psgc.address.parser import parse_address
        result = parse_address("Brgy. San Antonio, Makati City")
        assert result.barangay == "San Antonio"
        assert result.city == "Makati City"

    def test_numbered_barangay(self):
        from psgc.address.parser import parse_address
        result = parse_address("Brgy. 123, City of Manila")
        assert result.barangay == "Barangay 123"

    def test_zip_code(self):
        from psgc.address.parser import parse_address
        result = parse_address("Ermita, Manila 1000")
        assert result.zip_code == "1000"

    def test_street_extraction(self):
        from psgc.address.parser import parse_address
        result = parse_address("123 Rizal St., Brgy. San Antonio, Makati City")
        assert result.street is not None

    def test_city_of_format(self):
        from psgc.address.parser import parse_address
        result = parse_address("City of Manila")
        assert result.city is not None

    def test_raw_preserved(self):
        from psgc.address.parser import parse_address
        raw = "123 Rizal St., Brgy. San Antonio, Makati City"
        result = parse_address(raw)
        assert result.raw == raw

    def test_to_dict(self):
        from psgc.address.parser import parse_address
        result = parse_address("Brgy. San Antonio, Makati City")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "raw" in d
        assert "barangay" in d


class TestFormatter:
    def test_format_barangay_address(self):
        from psgc._loader import get_store
        from psgc.address.formatter import format_address
        store = get_store()
        brgy = store.barangays[0]
        address = format_address(barangay=brgy)
        assert brgy.name in address

    def test_format_city_address(self):
        from psgc._loader import get_store
        from psgc.address.formatter import format_address
        store = get_store()
        city = store.cities[0]
        address = format_address(city=city)
        assert city.name in address


class TestValidator:
    def test_valid_code(self):
        from psgc.address.validator import is_valid, validate
        from psgc._loader import get_store
        code = get_store().barangays[0].psgc_code
        assert is_valid(code)
        valid, reason = validate(code)
        assert valid
        assert "barangay" in reason.lower()

    def test_invalid_code(self):
        from psgc.address.validator import is_valid, validate
        assert not is_valid("0000000000")
        valid, reason = validate("0000000000")
        assert not valid

    def test_invalid_format(self):
        from psgc.address.validator import validate
        valid, reason = validate("abc")
        assert not valid
        assert "numeric" in reason.lower()

    def test_wrong_length(self):
        from psgc.address.validator import validate
        valid, reason = validate("12345")
        assert not valid
        assert "10 digits" in reason
