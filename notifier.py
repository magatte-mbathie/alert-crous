import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_telegram_message(text):
    """Envoie un message via le bot Telegram."""
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def notify_new_logements(logements):
    for logement in logements:
        message = (
            f"🏠 <b>Nouveau logement disponible !</b>\n\n"
            f"<b>{logement['title']}</b>\n"
            f"💰 {logement.get('price', 'N/A')}\n"
            f"📍 {logement.get('address', 'N/A')}\n"
            f"📐 {logement.get('surface', 'N/A')} - {logement.get('occupation', 'N/A')}\n\n"
            f"🔗 <a href=\"{logement['link']}\">Voir le logement</a>"
        )
        send_telegram_message(message)
