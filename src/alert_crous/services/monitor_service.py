import logging

from ..domain.models import Logement
from ..domain.ports import LogementRepository, Notifier, Scraper
from .detection_service import detect_new_logements

LOGGER = logging.getLogger(__name__)


class MonitorService:
    def __init__(self, scraper: Scraper, notifier: Notifier, repository: LogementRepository) -> None:
        self.scraper = scraper
        self.notifier = notifier
        self.repository = repository

    def run_once(self, urls: list[str]) -> list[Logement]:
        logements = self.fetch_all(urls)
        known_ids = self.repository.get_known_ids()
        current_ids = {logement.id for logement in logements}
        new_logements = detect_new_logements(logements, known_ids)
        removed_ids = known_ids - current_ids

        if new_logements:
            LOGGER.info("%s nouveau(x) logement(s) détecté(s)", len(new_logements))
            self.notifier.notify_new_logements(new_logements)

        if removed_ids:
            LOGGER.info(
                "%s logement(s) indisponible(s), conservation des notifications Discord",
                len(removed_ids),
            )

        self.repository.save_seen_ids(current_ids)
        return new_logements

    def fetch_all(self, urls: list[str]) -> list[Logement]:
        all_logements: list[Logement] = []
        seen_ids: set[str] = set()

        for url in urls:
            fetched = self.scraper.fetch_logements(url)
            for logement in fetched:
                if logement.id in seen_ids:
                    continue
                seen_ids.add(logement.id)
                all_logements.append(logement)

        return all_logements