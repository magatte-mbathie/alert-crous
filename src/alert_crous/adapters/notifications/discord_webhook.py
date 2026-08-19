import logging
from datetime import datetime
from typing import Any

import requests

from ...domain.models import Logement

LOGGER = logging.getLogger(__name__)
DISCORD_COLOR = 0x2ECC71
CROUS_SITE_URL = "https://trouverunlogement.lescrous.fr"


class DiscordWebhookNotifier:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url
        self._message_ids_by_logement_id: dict[str, str] = {}

    def notify_new_logements(self, logements: list[Logement]) -> None:
        for logement in logements:
            payload = {
                "content": "🏠 Nouveau logement disponible !",
                "embeds": [self._build_embed(logement)],
            }
            LOGGER.info("Envoi d'une notification Discord pour %s", logement.id)
            response = requests.post(self._with_wait_param(self.webhook_url), json=payload, timeout=10)
            if response.status_code >= 400:
                LOGGER.error(
                    "Discord refuse la notification (%s) pour %s: %s",
                    response.status_code,
                    logement.id,
                    response.text[:500],
                )
                continue

            data = self._safe_json(response)
            message_id = data.get("id") if isinstance(data, dict) else None
            if message_id:
                self._message_ids_by_logement_id[logement.id] = str(message_id)

    def remove_unavailable_logements(self, logement_ids: set[str]) -> None:
        for logement_id in logement_ids:
            message_id = self._message_ids_by_logement_id.pop(logement_id, None)
            if not message_id:
                continue

            delete_url = self._message_delete_url(message_id)
            response = requests.delete(delete_url, timeout=10)
            if response.status_code >= 400:
                LOGGER.error(
                    "Echec suppression Discord (%s) pour %s: %s",
                    response.status_code,
                    logement_id,
                    response.text[:500],
                )

    def _build_embed(self, logement: Logement) -> dict:
        embed = {
            "title": self._safe_text(logement.title, 256),
            "url": CROUS_SITE_URL,
            "color": DISCORD_COLOR,
            "fields": [
                {"name": "Prix", "value": self._safe_text(logement.price, 1024), "inline": True},
                {"name": "Type de logement", "value": self._safe_text(logement.logement_type, 1024), "inline": True},
                {"name": "Heure disponible", "value": self._available_time_text(logement.detected_at), "inline": True},
                {"name": "Adresse", "value": self._safe_text(logement.address, 1024), "inline": False},
                {"name": "Surface", "value": self._safe_text(logement.surface, 1024), "inline": True},
                {"name": "Occupation", "value": self._safe_text(logement.occupation, 1024), "inline": True},
                {"name": "Lien", "value": CROUS_SITE_URL, "inline": False},
            ],
        }

        if logement.image_url:
            embed["image"] = {"url": logement.image_url}

        return embed

    def _safe_text(self, value: str, max_length: int) -> str:
        if not value:
            return "N/A"
        text = str(value).strip()
        if not text:
            return "N/A"
        return text if len(text) <= max_length else text[: max_length - 1] + "…"

    def _with_wait_param(self, url: str) -> str:
        if "wait=" in url:
            return url
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}wait=true"

    def _available_time_text(self, detected_at: int | None) -> str:
        if not detected_at:
            return "N/A"
        return datetime.fromtimestamp(detected_at).strftime("%H:%M:%S")

    def _message_delete_url(self, message_id: str) -> str:
        webhook_base = self.webhook_url.split("?", 1)[0].rstrip("/")
        return f"{webhook_base}/messages/{message_id}"

    def _safe_json(self, response: requests.Response) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError:
            return {}