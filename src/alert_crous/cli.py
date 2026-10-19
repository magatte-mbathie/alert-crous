import logging
import sys
import time

from .adapters.notifications.discord_webhook import DiscordWebhookNotifier
from .adapters.persistence.sqlite_repository import SqliteLogementRepository
from .adapters.scraper.crous_scraper import fetch_logements
from .config import (
    CHECK_INTERVAL,
    CROUS_URLS,
    DISCORD_WEBHOOK_URL,
    LOG_LEVEL,
    MISS_THRESHOLD,
    NOTIFY_EXISTING_ON_STARTUP,
    STATE_DB_PATH,
    validate_crous_urls,
    validate_discord_webhook_url,
)
from .domain.models import Logement
from .logging_config import configure_logging
from .services.monitor_service import MonitorService


class CrousScraperAdapter:
    def fetch_logements(self, url: str) -> list[Logement]:
        return fetch_logements(url)


def main() -> None:
    configure_logging(LOG_LEVEL)
    logger = logging.getLogger(__name__)

    try:
        validate_discord_webhook_url(DISCORD_WEBHOOK_URL)
        validate_crous_urls(CROUS_URLS)
    except ValueError as error:
        logger.error("%s", error)
        sys.exit(1)

    logger.info("Démarrage de Alert CROUS")
    logger.info("Nombre d'URLs surveillées: %s", len(CROUS_URLS))
    logger.info("Intervalle: %ss", CHECK_INTERVAL)
    logger.info("Base d'état: %s", STATE_DB_PATH)

    scraper = CrousScraperAdapter()
    notifier = DiscordWebhookNotifier(DISCORD_WEBHOOK_URL)
    repository = SqliteLogementRepository(STATE_DB_PATH)
    service = MonitorService(
        scraper,
        notifier,
        repository,
        miss_threshold=MISS_THRESHOLD,
    )

    next_run = time.monotonic()
    try:
        while True:
            try:
                service.run_once(
                    CROUS_URLS,
                    notify_existing=NOTIFY_EXISTING_ON_STARTUP,
                )
            except Exception:
                logger.exception("Erreur lors du scan")

            next_run += CHECK_INTERVAL
            now = time.monotonic()
            if next_run <= now:
                next_run = now + CHECK_INTERVAL
            time.sleep(next_run - now)
    except KeyboardInterrupt:
        logger.info("Arrêt demandé")
