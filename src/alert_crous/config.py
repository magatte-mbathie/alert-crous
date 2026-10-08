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


DISCORD_WEBHOOK_URL = _clean_env_value(os.getenv("DISCORD_WEBHOOK_URL"))
CROUS_URL = _clean_env_value(os.getenv("CROUS_URL")) or "https://trouverunlogement.lescrous.fr/tools/47/search"
CROUS_URLS_RAW = _clean_env_value(os.getenv("CROUS_URLS")) or ""


def _parse_check_interval(raw: str | None) -> int:
    value = (raw or "5").strip()
    try:
        interval = int(value)
    except ValueError as error:
        raise ValueError("CHECK_INTERVAL doit être un entier positif exprimé en secondes") from error

    if interval <= 0:
        raise ValueError("CHECK_INTERVAL doit être supérieur à zéro")
    return interval


CHECK_INTERVAL = _parse_check_interval(os.getenv("CHECK_INTERVAL"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DATABASE_URL = _clean_env_value(os.getenv("DATABASE_URL"))
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