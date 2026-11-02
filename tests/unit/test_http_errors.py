import requests

from alert_crous.http_errors import (
    format_request_error,
    is_connectivity_error,
    is_retryable_request_error,
    short_error,
    url_label,
)


def http_error(status_code: int, reason: str = "") -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status_code
    response.reason = reason
    return requests.HTTPError(response=response)


def test_connection_refused_is_reported_concisely():
    error = requests.ConnectionError(
        "HTTPSConnectionPool(host='example.com', port=443): Max retries exceeded "
        "(Caused by NewConnectionError('Connection refused'))"
    )

    assert format_request_error(error) == "connexion refusée"
    assert is_connectivity_error(error) is True
    assert is_retryable_request_error(error) is True


def test_dns_failure_is_reported_concisely():
    error = requests.ConnectionError(
        "Failed to establish a new connection: "
        "[Errno -2] Name or service not known"
    )

    assert format_request_error(error) == "nom de domaine introuvable"


def test_timeout_is_reported_concisely():
    assert format_request_error(requests.Timeout("read timed out")) == "délai dépassé"


def test_http_error_is_reported_concisely():
    assert format_request_error(http_error(503, "Service Unavailable")) == (
        "HTTP 503 Service Unavailable"
    )


def test_only_transient_http_errors_are_retried():
    assert is_retryable_request_error(http_error(404, "Not Found")) is False
    assert is_retryable_request_error(http_error(429, "Too Many Requests")) is True
    assert is_retryable_request_error(http_error(503, "Service Unavailable")) is True


def test_short_error_uses_the_exception_class_when_message_is_empty():
    assert short_error(RuntimeError()) == "RuntimeError"


def test_short_error_truncates_long_messages():
    message = short_error(RuntimeError("x" * 500))

    assert len(message) == 200
    assert message.endswith("…")


def test_url_label_prefers_the_location_name():
    url = (
        "https://trouverunlogement.lescrous.fr/tools/47/search"
        "?bounds=1_2_3_4&locationName=Villeneuve-d%27Ascq+%2859260%29"
    )

    assert url_label(url) == "Villeneuve-d'Ascq (59260)"


def test_url_label_falls_back_to_the_path():
    assert url_label("https://trouverunlogement.lescrous.fr/tools/47/search?bounds=1") == (
        "tools/47/search"
    )
