import pytest

from alert_crous.config import (
    _parse_check_interval,
    _parse_positive_int,
    validate_crous_urls,
)


def test_parse_check_interval_defaults_to_five_seconds():
    assert _parse_check_interval(None) == 5


def test_parse_check_interval_accepts_positive_integer():
    assert _parse_check_interval("120") == 120


@pytest.mark.parametrize("value", ["0", "-1"])
def test_parse_check_interval_rejects_non_positive_values(value):
    with pytest.raises(ValueError, match="supérieur à zéro"):
        _parse_check_interval(value)


def test_parse_check_interval_rejects_non_integer():
    with pytest.raises(ValueError, match="entier positif"):
        _parse_check_interval("abc")


def test_parse_positive_int_rejects_invalid_values():
    with pytest.raises(ValueError, match="entier positif"):
        _parse_positive_int("abc", "MISS_THRESHOLD", 2)
    with pytest.raises(ValueError, match="supérieur à zéro"):
        _parse_positive_int("0", "MISS_THRESHOLD", 2)


def test_validate_crous_urls_rejects_example_placeholders():
    with pytest.raises(ValueError, match="valeur d'exemple"):
        validate_crous_urls(["https://trouverunlogement.lescrous.fr/tools/47/search?bounds=..."])


def test_validate_crous_urls_rejects_non_http_url():
    with pytest.raises(ValueError, match="URL CROUS invalide"):
        validate_crous_urls(["file:///tmp/search"])


def test_validate_crous_urls_accepts_real_url():
    validate_crous_urls(
        ["https://trouverunlogement.lescrous.fr/tools/47/search?bounds=1_2_3_4"]
    )
