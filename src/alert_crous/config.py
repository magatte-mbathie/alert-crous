import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
CROUS_URL = os.getenv("CROUS_URL", "https://trouverunlogement.lescrous.fr/tools/47/search")
CROUS_URLS_RAW = os.getenv("CROUS_URLS", "")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DATABASE_URL = os.getenv("DATABASE_URL")
NOTIFY_EXISTING_ON_STARTUP = os.getenv("NOTIFY_EXISTING_ON_STARTUP", "false").strip().lower() in {
	"1",
	"true",
	"yes",
	"on",
}


def _parse_crous_urls(raw: str) -> list[str]:
    values = [part.strip() for part in raw.replace("\n", ",").split(",")]
    return [value for value in values if value]


CROUS_URLS = _parse_crous_urls(CROUS_URLS_RAW) or [CROUS_URL]