import logging

import requests

from ...domain.models import Logement

LOGGER = logging.getLogger(__name__)
DISCORD_COLOR = 0x2ECC71


class DiscordWebhookNotifier:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

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

    def _build_embed(self, logement: Logement) -> dict:
        embed = {
            "title": self._safe_text(logement.title, 256),
            "url": logement.link,
            "color": DISCORD_COLOR,
            "fields": [
                {"name": "Prix", "value": self._safe_text(logement.price, 1024), "inline": True},
                {"name": "Type de logement", "value": self._safe_text(logement.logement_type, 1024), "inline": True},
                {"name": "Adresse", "value": self._safe_text(logement.address, 1024), "inline": False},
                {"name": "Surface", "value": self._safe_text(logement.surface, 1024), "inline": True},
                {"name": "Occupation", "value": self._safe_text(logement.occupation, 1024), "inline": True},
                {"name": "Lien", "value": self._safe_text(logement.link, 1024), "inline": False},
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