import logging
import time
from dataclasses import replace

from ..domain.models import Logement
from ..domain.ports import LogementRepository, Notifier, Scraper
from ..domain.state import RepositoryState, StoredLogement

LOGGER = logging.getLogger(__name__)


class MonitorService:
    def __init__(
        self,
        scraper: Scraper,
        notifier: Notifier,
        repository: LogementRepository,
        miss_threshold: int = 2,
    ) -> None:
        if miss_threshold < 1:
            raise ValueError("miss_threshold doit être supérieur à zéro")
        self.scraper = scraper
        self.notifier = notifier
        self.repository = repository
        self.miss_threshold = miss_threshold

    def run_once(self, urls: list[str], notify_existing: bool = True) -> list[Logement]:
        state = self.repository.load_state()
        active_urls = set(urls)
        self._prune_stale_urls(state, active_urls)

        is_initial = not state.logements and not state.url_ids
        fetched: dict[str, list[Logement]] = {}
        failed_urls: set[str] = set()

        for url in urls:
            try:
                fetched[url] = self.scraper.fetch_logements(url)
            except Exception:
                failed_urls.add(url)
                LOGGER.exception("Échec du scan de %s, état de cette URL conservé", url)

        if not fetched:
            LOGGER.error("Aucune URL n'a pu être scannée, état inchangé")
            return []

        now = int(time.time())
        current_ids_by_url = {
            url: {logement.id for logement in logements}
            for url, logements in fetched.items()
        }

        known_ids: set[str] = set()
        for ids in current_ids_by_url.values():
            known_ids |= ids
        for url in failed_urls:
            known_ids |= state.url_ids.get(url, set())

        new_by_id: dict[str, Logement] = {}
        for logements in fetched.values():
            for logement in logements:
                stored = state.logements.get(logement.id)
                if stored is None or not stored.available:
                    new_by_id[logement.id] = replace(logement, detected_at=now)
                else:
                    stored.logement = replace(
                        logement,
                        detected_at=stored.logement.detected_at,
                    )

        pending = [
            stored.logement
            for logement_id, stored in state.logements.items()
            if stored.available
            and stored.notification_status == "pending"
            and logement_id in known_ids
            and logement_id not in new_by_id
        ]

        candidates = list(new_by_id.values()) + pending
        if is_initial and not notify_existing:
            for logement in candidates:
                state.logements[logement.id] = StoredLogement(
                    logement=logement,
                    notification_status="ignored",
                    available=True,
                )
            LOGGER.info(
                "Premier scan: %s logement(s) existant(s) marqué(s) comme vus sans notification",
                len(candidates),
            )
            candidates = []

        notified_count = 0
        for logement in candidates:
            try:
                message_id = self.notifier.notify_logement(logement)
            except Exception:
                LOGGER.exception(
                    "Erreur inattendue lors de la notification de %s",
                    logement.id,
                )
                message_id = None

            if message_id:
                state.logements[logement.id] = StoredLogement(
                    logement=logement,
                    message_id=message_id,
                    notification_status="sent",
                    available=True,
                )
                notified_count += 1
            else:
                state.logements[logement.id] = StoredLogement(
                    logement=logement,
                    notification_status="pending",
                    available=True,
                )

            # Persiste immédiatement pour ne pas renvoyer une alerte déjà
            # envoyée si le processus s'arrête pendant un scan.
            self.repository.save_state(state)

        for url, ids in current_ids_by_url.items():
            state.url_ids[url] = ids

        known_after_scan: set[str] = set()
        for ids in state.url_ids.values():
            known_after_scan |= ids

        unavailable_count = 0
        for logement_id, stored in state.logements.items():
            if not stored.available:
                continue

            if logement_id in known_after_scan:
                stored.miss_count = 0
                continue

            stored.miss_count += 1
            if stored.miss_count < self.miss_threshold:
                LOGGER.debug(
                    "Logement %s absent (%s/%s), confirmation en attente",
                    logement_id,
                    stored.miss_count,
                    self.miss_threshold,
                )
                continue

            if stored.message_id and stored.notification_status == "sent":
                try:
                    marked = self.notifier.mark_unavailable(
                        stored.logement,
                        stored.message_id,
                    )
                except Exception:
                    LOGGER.exception(
                        "Erreur inattendue lors de la mise à jour de %s",
                        logement_id,
                    )
                    marked = False
                if not marked:
                    LOGGER.warning(
                        "Impossible de marquer le logement %s indisponible, nouvelle tentative au prochain scan",
                        logement_id,
                    )
                    continue

            stored.available = False
            stored.miss_count = self.miss_threshold
            unavailable_count += 1

        self.repository.save_state(state)

        log_message = (
            "Scan: %s URL(s) OK, %s en erreur, %s nouveau(x), %s notifié(s), %s indisponible(s)"
        )
        log_args = (
            len(fetched),
            len(failed_urls),
            len(new_by_id),
            notified_count,
            unavailable_count,
        )
        if new_by_id or unavailable_count or failed_urls:
            LOGGER.info(log_message, *log_args)
        else:
            LOGGER.debug(log_message, *log_args)

        return list(new_by_id.values())

    def _prune_stale_urls(self, state: RepositoryState, active_urls: set[str]) -> None:
        for stale_url in set(state.url_ids) - active_urls:
            LOGGER.info("URL retirée de la surveillance: %s", stale_url)
            del state.url_ids[stale_url]
