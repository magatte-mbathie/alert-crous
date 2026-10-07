import pytest

from alert_crous.config import _parse_check_interval


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
