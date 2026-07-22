import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CROUS_URL = os.getenv("CROUS_URL", "https://trouverunlogement.lescrous.fr/tools/47/search")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))
