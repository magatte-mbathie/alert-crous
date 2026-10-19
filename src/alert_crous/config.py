import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def _clean_env_value(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()
    cleaned = cleaned.strip('"').strip("'")

    return cleaned or None


def _parse_positive_int(raw: str | None, name: str, default: int) -> int:
    value = (raw or str(default)).strip()
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{name} doit être un entier positif") from error

    if parsed <= 0:
        raise ValueError(f"{name} doit être supérieur à zéro")
    return parsed


def _parse_check_interval(raw: str | None) -> int:
    return _parse_positive_int(raw, "CHECK_INTERVAL", 5)


DISCORD_WEBHOOK_URL = _clean_env_value(os.getenv("DISCORD_WEBHOOK_URL"))
CROUS_URL = _clean_env_value(os.getenv("CROUS_URL")) or "https://trouverunlogement.lescrous.fr/tools/47/search?bounds=2.9849982015429077_50.780121396973215_3.248670076542908_50.55817291054383&locationName=Lille"
CROUS_URLS_RAW = _clean_env_value(os.getenv("CROUS_URLS")) or ""

CHECK_INTERVAL = _parse_check_interval(os.getenv("CHECK_INTERVAL"))
MISS_THRESHOLD = _parse_positive_int(os.getenv("MISS_THRESHOLD"), "MISS_THRESHOLD", 2)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
STATE_DB_PATH = _clean_env_value(os.getenv("STATE_DB_PATH")) or str(
    BASE_DIR / "data" / "alert_crous.sqlite3"
)
NOTIFY_EXISTING_ON_STARTUP = os.getenv("NOTIFY_EXISTING_ON_STARTUP", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _parse_crous_urls(raw: str) -> list[str]:
    values = [part.strip() for part in raw.replace("\n", ",").split(",")]
    return [value for value in values if value]


CROUS_URLS = _parse_crous_urls(CROUS_URLS_RAW) or [CROUS_URL]


def validate_crous_urls(urls: list[str]) -> None:
    for url in urls:
        if "..." in url or "TON_" in url:
            raise ValueError(
                "CROUS_URL contient encore une valeur d'exemple. "
                "Renseignez une URL de recherche CROUS valide dans .env."
            )
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"URL CROUS invalide: {url}")
