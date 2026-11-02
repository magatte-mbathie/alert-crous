"""Résumés courts et lisibles des erreurs réseau destinés aux logs."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlsplit

import requests
from requests import exceptions as requests_exceptions

MAX_ERROR_LENGTH = 200
MAX_URL_LABEL_LENGTH = 120


def format_request_error(error: requests.RequestException) -> str:
    """Transforme une exception requests en message court et compréhensible."""
    if isinstance(error, requests.HTTPError):
        response = error.response
        if response is None:
            return "erreur HTTP"
        reason = str(response.reason or "").strip()
        suffix = f" {reason}" if reason else ""
        return _truncate(f"HTTP {response.status_code}{suffix}")

    if isinstance(error, requests.Timeout):
        return "délai dépassé"

    if isinstance(error, requests_exceptions.SSLError):
        return "erreur TLS"

    if isinstance(error, requests.ConnectionError):
        text = str(error).lower()
        if "connection refused" in text or "errno 111" in text:
            return "connexion refusée"
        if any(
            marker in text
            for marker in (
                "name or service not known",
                "nodename nor servname",
                "temporary failure in name resolution",
                "getaddrinfo failed",
                "name resolution",
            )
        ):
            return "nom de domaine introuvable"
        if "certificate" in text:
            return "certificat TLS invalide"
        if "timed out" in text or "timeout" in text:
            return "délai de connexion dépassé"
        return "connexion impossible"

    return short_error(error)


def is_connectivity_error(error: requests.RequestException) -> bool:
    """Indique si l'erreur signifie que le site est globalement injoignable."""
    return isinstance(error, (requests.ConnectionError, requests.Timeout))


def is_retryable_request_error(error: requests.RequestException) -> bool:
    """Indique si une nouvelle tentative peut raisonnablement réussir."""
    if isinstance(error, requests.HTTPError):
        response = error.response
        if response is None:
            return True
        return response.status_code in {408, 429} or 500 <= response.status_code < 600
    return is_connectivity_error(error)


def short_error(error: BaseException) -> str:
    """Retourne la première ligne d'une erreur, sans coupure au milieu d'un mot."""
    message = " ".join(str(error).split())
    if not message:
        return error.__class__.__name__
    return _truncate(message)


def url_label(url: str) -> str:
    """Retourne le nom de la recherche CROUS, ou une URL compacte."""
    try:
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
    except ValueError:
        return _truncate(url, MAX_URL_LABEL_LENGTH)

    location = query.get("locationName", "").strip()
    if location:
        return _truncate(location, MAX_URL_LABEL_LENGTH)

    path = parts.path.strip("/")
    if path:
        return _truncate(path, MAX_URL_LABEL_LENGTH)
    return _truncate(url, MAX_URL_LABEL_LENGTH)


def _truncate(value: str, max_length: int = MAX_ERROR_LENGTH) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 1] + "…"
