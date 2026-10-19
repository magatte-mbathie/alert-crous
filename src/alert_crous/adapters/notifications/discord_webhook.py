import logging
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from ...domain.models import Logement

LOGGER = logging.getLogger(__name__)
DISCORD_COLOR = 0x2ECC71
DISCORD_UNAVAILABLE_COLOR = 0xE74C3C
MAX_ATTEMPTS = 3
MAX_RETRY_AFTER_SECONDS = 300.0


class DiscordWebhookNotifier:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = self._normalize_webhook_url(webhook_url)

    def notify_logement(self, logement: Logement) -> str | None:
        payload = {
            "content": "🏠 Nouveau logement disponible !",
            "embeds": [self._build_embed(logement)],
        }
        LOGGER.debug("Envoi d'une notification Discord pour %s", logement.id)

        response = self._request_with_retries(
            "POST",
            self._with_wait_param(self.webhook_url),
            json=payload,
        )
        if response is None or response.status_code >= 400:
            self._log_discord_error("notification", logement.id, response)
            return None

        data = self._safe_json(response)
        message_id = data.get("id") if isinstance(data, dict) else None
        if not message_id:
            LOGGER.error("Discord n'a pas renvoyé d'identifiant de message pour %s", logement.id)
            return None

        return str(message_id)

    def mark_unavailable(self, logement: Logement, message_id: str) -> bool:
        payload = {
            "content": "🏠 Nouveau logement disponible !",
            "embeds": [self._build_embed(logement)],
        }
        unavailable_payload = self._build_unavailable_payload(payload)
        response = self._request_with_retries(
            "PATCH",
            self._message_edit_url(message_id),
            json=unavailable_payload,
        )
        if response is None:
            self._log_discord_error("mise à jour", logement.id, response)
            return False
        if response.status_code == 404:
            LOGGER.warning(
                "Message Discord introuvable pour %s; logement considéré comme traité",
                logement.id,
            )
            return True
        if response.status_code >= 400:
            self._log_discord_error("mise à jour", logement.id, response)
            return False

        return True

    def _request_with_retries(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> requests.Response | None:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = requests.request(method, url, timeout=10, **kwargs)
            except requests.RequestException as error:
                if attempt >= MAX_ATTEMPTS:
                    LOGGER.error("Échec Discord après %s tentatives: %s", MAX_ATTEMPTS, error)
                    return None
                backoff = 2 ** (attempt - 1)
                LOGGER.warning(
                    "Erreur réseau Discord (tentative %s/%s), nouvelle tentative dans %ss: %s",
                    attempt,
                    MAX_ATTEMPTS,
                    backoff,
                    error,
                )
                time.sleep(backoff)
                continue

            if response.status_code == 429:
                if attempt >= MAX_ATTEMPTS:
                    return response
                retry_after = self._retry_after(response)
                LOGGER.warning(
                    "Discord limite le débit (tentative %s/%s), pause de %.2fs",
                    attempt,
                    MAX_ATTEMPTS,
                    retry_after,
                )
                time.sleep(retry_after)
                continue

            if 500 <= response.status_code < 600:
                if attempt >= MAX_ATTEMPTS:
                    return response
                backoff = 2 ** (attempt - 1)
                LOGGER.warning(
                    "Erreur serveur Discord %s (tentative %s/%s), nouvelle tentative dans %ss",
                    response.status_code,
                    attempt,
                    MAX_ATTEMPTS,
                    backoff,
                )
                time.sleep(backoff)
                continue

            return response

        return None

    def _retry_after(self, response: requests.Response) -> float:
        data = self._safe_json(response)
        value = data.get("retry_after") if isinstance(data, dict) else None
        if value is None:
            value = response.headers.get("Retry-After")
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            seconds = 1.0
        return min(max(seconds, 0.1), MAX_RETRY_AFTER_SECONDS)

    def _log_discord_error(
        self,
        action: str,
        logement_id: str,
        response: requests.Response | None,
    ) -> None:
        if response is None:
            LOGGER.error("Échec de la %s Discord pour %s", action, logement_id)
            return
        LOGGER.error(
            "Discord refuse la %s (%s) pour %s: %s",
            action,
            response.status_code,
            logement_id,
            (getattr(response, "text", "") or "")[:500],
        )

    def _build_embed(self, logement: Logement) -> dict:
        embed = {
            "title": self._safe_text(logement.title, 256),
            "url": logement.link,
            "color": DISCORD_COLOR,
            "fields": [
                self._field("Prix", logement.price, inline=True),
                self._field("Type de logement", logement.logement_type, inline=True),
                self._field(
                    "Heure disponible",
                    self._available_time_text(logement.detected_at),
                    inline=True,
                ),
                self._field("Adresse", logement.address, inline=False),
                self._field("Surface", logement.surface, inline=True),
                self._field("Occupation", logement.occupation, inline=True),
                self._field("Lien", logement.link, inline=False),
            ],
        }

        if logement.image_url:
            embed["image"] = {"url": logement.image_url}

        return embed

    def _field(self, name: str, value: str, inline: bool) -> dict:
        return {
            "name": name,
            "value": self._safe_text(value, 1024),
            "inline": inline,
        }

    def _safe_text(self, value: str, max_length: int) -> str:
        if not value:
            return "N/A"
        text = str(value).strip()
        if not text:
            return "N/A"
        return text if len(text) <= max_length else text[: max_length - 1] + "…"

    def _with_wait_param(self, url: str) -> str:
        parts = urlsplit(url)
        query = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key != "wait"
        ]
        query.append(("wait", "true"))
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )

    def _available_time_text(self, detected_at: int | None) -> str:
        if not detected_at:
            return "N/A"
        return f"<t:{detected_at}:t>"

    def _message_edit_url(self, message_id: str) -> str:
        webhook_base = self.webhook_url.split("?", 1)[0].rstrip("/")
        return f"{webhook_base}/messages/{message_id}"

    def _build_unavailable_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        embeds = [dict(embed) for embed in payload.get("embeds", [])]
        for embed in embeds:
            embed["color"] = DISCORD_UNAVAILABLE_COLOR
            embed["footer"] = {"text": "⛔ Logement déjà pris"}

        return {
            "content": "⛔ Ce logement est déjà pris et n'est plus disponible.",
            "embeds": embeds,
        }

    def _normalize_webhook_url(self, url: str) -> str:
        cleaned = url.strip()
        cleaned = cleaned.strip('"').strip("'")
        return cleaned

    def _safe_json(self, response: requests.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}
