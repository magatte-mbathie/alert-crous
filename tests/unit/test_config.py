import pytest

from alert_crous.config import (
    _parse_check_interval,
    _parse_positive_int,
    validate_crous_urls,
    validate_discord_webhook_url,
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


def test_validate_discord_webhook_url_requires_a_value():
    with pytest.raises(ValueError, match="doit être défini"):
        validate_discord_webhook_url(None)


def test_validate_discord_webhook_url_rejects_the_example():
    with pytest.raises(ValueError, match="valeur d'exemple"):
        validate_discord_webhook_url(
            "https://discord.com/api/webhooks/TON_ID/TON_TOKEN"
        )


def test_validate_discord_webhook_url_requires_https():
    with pytest.raises(ValueError, match="HTTPS"):
        validate_discord_webhook_url("http://discord.com/api/webhooks/1/2")


def test_validate_discord_webhook_url_accepts_a_real_url():
    validate_discord_webhook_url("https://discord.com/api/webhooks/123/abc")
