import math
import os
import re
from collections.abc import Mapping
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

DEFAULT_CHECK_INTERVAL = 3.0
MIN_CHECK_INTERVAL = 1.0

_NUMBERED_URL_PATTERN = re.compile(r"^(?:CROUS_)?URL_?(\d+)$", re.IGNORECASE)


def _clean_env_value(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()
    cleaned = cleaned.strip('"').strip("'")

    return cleaned or None


def _parse_positive_int(raw: str | None, name: str, default: int) -> int:
    value = (_clean_env_value(raw) or str(default)).strip()
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{name} doit être un entier positif") from error

    if parsed <= 0:
        raise ValueError(f"{name} doit être supérieur à zéro")
    return parsed


def _parse_check_interval(raw: str | None) -> float:
    value = (_clean_env_value(raw) or str(DEFAULT_CHECK_INTERVAL)).strip()
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError("CHECK_INTERVAL doit être un nombre positif") from error

    if not math.isfinite(parsed) or parsed < MIN_CHECK_INTERVAL:
        raise ValueError(
            f"CHECK_INTERVAL doit être au moins {MIN_CHECK_INTERVAL:g} seconde"
        )
    return parsed


CROUS_URL = _clean_env_value(os.getenv("CROUS_URL"))
DISCORD_WEBHOOK_URL = _clean_env_value(os.getenv("DISCORD_WEBHOOK_URL"))
CHECK_INTERVAL = _parse_check_interval(os.getenv("CHECK_INTERVAL"))
MISS_THRESHOLD = _parse_positive_int(os.getenv("MISS_THRESHOLD"), "MISS_THRESHOLD", 2)
LOG_LEVEL = (_clean_env_value(os.getenv("LOG_LEVEL")) or "INFO").upper()
STATE_DB_PATH = _clean_env_value(os.getenv("STATE_DB_PATH")) or str(
    BASE_DIR / "data" / "alert_crous.sqlite3"
)
NOTIFY_EXISTING_ON_STARTUP = (
    _clean_env_value(os.getenv("NOTIFY_EXISTING_ON_STARTUP")) or "true"
).lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _parse_crous_urls(raw: str) -> list[str]:
    values = [_clean_env_value(part) for part in raw.replace("\n", ",").split(",")]
    return [value for value in values if value]


def _collect_crous_urls(environ: Mapping[str, str]) -> list[str]:
    """Lit URL1, URL2, ... puis les anciennes variables CROUS_URL/URLS."""
    numbered_urls: list[tuple[int, str]] = []
    for key, value in environ.items():
        match = _NUMBERED_URL_PATTERN.match(key)
        if not match:
            continue

        cleaned = _clean_env_value(value)
        if cleaned:
            numbered_urls.append((int(match.group(1)), cleaned))

    numbered_urls.sort(key=lambda item: item[0])
    if numbered_urls:
        return _deduplicate_urls([value for _, value in numbered_urls])

    urls = _parse_crous_urls(environ.get("CROUS_URLS", ""))
    single_url = _clean_env_value(environ.get("CROUS_URL"))
    if single_url:
        urls.append(single_url)

    return _deduplicate_urls(urls)


def _deduplicate_urls(urls: list[str]) -> list[str]:
    unique_urls: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        unique_urls.append(url)

    return unique_urls


CROUS_URLS = _collect_crous_urls(os.environ)


def validate_discord_webhook_url(url: str | None) -> None:
    if not url:
        raise ValueError("DISCORD_WEBHOOK_URL doit être défini dans .env")
    if "TON_" in url:
        raise ValueError(
            "DISCORD_WEBHOOK_URL contient encore la valeur d'exemple. "
            "Renseignez l'URL réelle du webhook Discord."
        )
    if not url.startswith("https://"):
        raise ValueError("DISCORD_WEBHOOK_URL doit être une URL HTTPS")


def validate_crous_urls(urls: list[str]) -> None:
    if not urls:
        raise ValueError(
            "Au moins une URL CROUS doit être définie dans .env "
            "(URL1, URL2, ... ou CROUS_URL/CROUS_URLS)"
        )

    for url in urls:
        if "..." in url or "TON_" in url:
            raise ValueError(
                "Une URL CROUS contient encore une valeur d'exemple. "
                "Renseignez une URL de recherche CROUS valide dans .env."
            )
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"URL CROUS invalide: {url}")
