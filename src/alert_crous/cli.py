import logging
import sys
import time

from .adapters.notifications.discord_webhook import DiscordWebhookNotifier
from .adapters.persistence.memory_repository import InMemoryLogementRepository
from .adapters.scraper.crous_scraper import fetch_logements
from .config import (
    CHECK_INTERVAL,
    CROUS_URLS,
    DISCORD_WEBHOOK_URL,
    LOG_LEVEL,
    NOTIFY_EXISTING_ON_STARTUP,
)
from .logging_config import configure_logging
from .services.monitor_service import MonitorService


class CrousScraperAdapter:
    def fetch_logements(self, url: str):
        return fetch_logements(url)


def main() -> None:
    configure_logging(LOG_LEVEL)
    logger = logging.getLogger(__name__)

    if not DISCORD_WEBHOOK_URL:
        logger.error("DISCORD_WEBHOOK_URL doit être défini dans .env")
        sys.exit(1)

    logger.info("Démarrage de Alert CROUS")
    logger.info("Nombre d'URLs surveillées: %s", len(CROUS_URLS))
    logger.info("Intervalle: %ss", CHECK_INTERVAL)

    scraper = CrousScraperAdapter()
    notifier = DiscordWebhookNotifier(DISCORD_WEBHOOK_URL)
    repository = InMemoryLogementRepository()
    service = MonitorService(scraper, notifier, repository)

    try:
        initial_logements = service.fetch_all(CROUS_URLS)
        repository.save_seen_ids({logement.id for logement in initial_logements})
        logger.info("Initialisation terminée avec %s logement(s)", len(initial_logements))
        if NOTIFY_EXISTING_ON_STARTUP and initial_logements:
            logger.info("Notification des logements déjà disponibles au démarrage")
            notifier.notify_new_logements(initial_logements)
    except Exception:
        logger.exception("Erreur lors du premier scan")

    while True:
        try:
            service.run_once(CROUS_URLS)
            logger.info("Scan terminé avec succès")
        except Exception:
            logger.exception("Erreur lors du scan")

        time.sleep(CHECK_INTERVAL)