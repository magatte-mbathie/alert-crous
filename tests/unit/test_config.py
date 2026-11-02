import pytest

from alert_crous.config import (
    DEFAULT_CHECK_INTERVAL,
    _collect_crous_urls,
    _parse_check_interval,
    _parse_positive_int,
    validate_crous_urls,
    validate_discord_webhook_url,
)


def test_parse_check_interval_defaults_to_three_seconds():
    assert _parse_check_interval(None) == DEFAULT_CHECK_INTERVAL == 3.0


def test_parse_check_interval_accepts_positive_number():
    assert _parse_check_interval("120") == 120.0
    assert _parse_check_interval("2.5") == 2.5


@pytest.mark.parametrize("value", ["0", "-1", "0.5", "nan", "inf"])
def test_parse_check_interval_rejects_too_small_values(value):
    with pytest.raises(ValueError, match="au moins"):
        _parse_check_interval(value)


def test_parse_check_interval_rejects_non_number():
    with pytest.raises(ValueError, match="nombre positif"):
        _parse_check_interval("abc")


def test_parse_positive_int_rejects_invalid_values():
    with pytest.raises(ValueError, match="entier positif"):
        _parse_positive_int("abc", "MISS_THRESHOLD", 2)
    with pytest.raises(ValueError, match="supérieur à zéro"):
        _parse_positive_int("0", "MISS_THRESHOLD", 2)


def test_collect_crous_urls_reads_numbered_variables_in_order():
    urls = _collect_crous_urls(
        {
            "URL2": "https://example.com/2",
            "URL10": "https://example.com/10",
            "URL1": "https://example.com/1",
        }
    )

    assert urls == [
        "https://example.com/1",
        "https://example.com/2",
        "https://example.com/10",
    ]


def test_collect_crous_urls_accepts_lowercase_variables():
    urls = _collect_crous_urls(
        {
            "url1": "https://example.com/1",
            "url2": "https://example.com/2",
        }
    )

    assert urls == ["https://example.com/1", "https://example.com/2"]


def test_collect_crous_urls_supports_crous_url_prefix_and_deduplicates():
    urls = _collect_crous_urls(
        {
            "URL1": "https://example.com/1",
            "CROUS_URL1": "https://example.com/1",
        }
    )

    assert urls == ["https://example.com/1"]


def test_collect_crous_urls_prefers_numbered_variables_over_legacy():
    urls = _collect_crous_urls(
        {
            "URL1": "https://example.com/1",
            "CROUS_URLS": "https://example.com/2",
            "CROUS_URL": "https://example.com/3",
        }
    )

    assert urls == ["https://example.com/1"]


def test_collect_crous_urls_keeps_legacy_variables():
    urls = _collect_crous_urls(
        {
            "CROUS_URLS": "https://example.com/1,https://example.com/2",
            "CROUS_URL": "https://example.com/3",
        }
    )

    assert urls == [
        "https://example.com/1",
        "https://example.com/2",
        "https://example.com/3",
    ]


def test_collect_crous_urls_returns_empty_without_configuration():
    assert _collect_crous_urls({}) == []


def test_validate_crous_urls_requires_at_least_one_url():
    with pytest.raises(ValueError, match="Au moins une URL"):
        validate_crous_urls([])


def test_validate_crous_urls_rejects_example_placeholders():
    with pytest.raises(ValueError, match="valeur d'exemple"):
        validate_crous_urls(
            ["https://trouverunlogement.lescrous.fr/tools/47/search?bounds=..."]
        )


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


def test_cli_module_can_be_imported():
    import alert_crous.cli  # noqa: F401
