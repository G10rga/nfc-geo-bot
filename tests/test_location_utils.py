from location_utils import (
    detect_district,
    format_general_location,
    has_district,
    normalize_city,
)


def test_normalize_city_english_and_georgian():
    assert normalize_city("tbilisi") == "Tbilisi"
    assert normalize_city("თბილისი") == "Tbilisi"
    assert normalize_city("Tbilisi, Saburtalo") == "Tbilisi"


def test_normalize_city_empty():
    assert normalize_city("") == ""
    assert normalize_city("   ") == ""


def test_detect_district_prefers_longer_alias():
    assert detect_district("Vake-Saburtalo, Tbilisi") == "Saburtalo"
    assert detect_district("საბურთალო") == "Saburtalo"
    assert detect_district("somewhere in Vera") == "Vera"


def test_detect_district_empty():
    assert detect_district("") == ""
    assert detect_district() == ""


def test_format_general_location_with_district():
    assert (
        format_general_location(
            city_hint="Tbilisi",
            address="12 Rustaveli Ave, Saburtalo, Tbilisi",
        )
        == "Tbilisi, Saburtalo"
    )


def test_format_general_location_city_only():
    assert format_general_location(city_hint="Tbilisi", address="") == "Tbilisi"
    assert format_general_location() == "Tbilisi"


def test_has_district():
    assert has_district("Tbilisi, Saburtalo") is True
    assert has_district("Tbilisi") is False
    assert has_district("") is False
