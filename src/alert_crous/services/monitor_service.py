import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace

from ..domain.models import Logement
from ..domain.ports import LogementRepository, Notifier, Scraper
from ..domain.state import RepositoryState, StoredLogement
from ..http_errors import short_error, url_label

LOGGER = logging.getLogger(__name__)
MAX_CONCURRENT_URL_FETCHES = 4
FAILURE_LOG_INTERVAL_SECONDS = 300.0


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
        self._failure_logs: dict[str, tuple[str, float]] = {}
        self._all_failed_logged = False

    def run_once(self, urls: list[str], notify_existing: bool = True) -> list[Logement]:
        state = self.repository.load_state()
        active_urls = set(urls)
        self._prune_stale_urls(state, active_urls)

        is_initial = not state.logements and not state.url_ids
        fetched: dict[str, list[Logement]] = {}
        failed_urls: set[str] = set()

        if urls:
            max_workers = min(MAX_CONCURRENT_URL_FETCHES, len(urls))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self.scraper.fetch_logements, url): url
                    for url in urls
                }
                for future in as_completed(futures):
                    url = futures[future]
                    try:
                        fetched[url] = future.result()
                    except Exception as error:
                        failed_urls.add(url)
                        self._log_scan_failure(url, error)
                    else:
                        self._log_scan_recovery(url)

        if not fetched:
            if not self._all_failed_logged:
                LOGGER.error("Aucune URL n'a pu être scannée, état inchangé")
                self._all_failed_logged = True
            else:
                LOGGER.debug("Aucune URL n'a pu être scannée, état inchangé")
            return []

        self._all_failed_logged = False

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

    def _log_scan_failure(self, url: str, error: Exception) -> None:
        reason = short_error(error)
        label = url_label(url)
        now = time.monotonic()
        previous = self._failure_logs.get(url)
        should_log = (
            previous is None
            or previous[0] != reason
            or now - previous[1] >= FAILURE_LOG_INTERVAL_SECONDS
        )

        if not should_log:
            LOGGER.debug("Scan toujours impossible pour %s: %s", label, reason)
            return

        self._failure_logs[url] = (reason, now)
        LOGGER.warning(
            "Scan impossible pour %s: %s (état conservé)",
            label,
            reason,
            exc_info=LOGGER.isEnabledFor(logging.DEBUG),
        )

    def _log_scan_recovery(self, url: str) -> None:
        if self._failure_logs.pop(url, None) is not None:
            LOGGER.info("Scan rétabli pour %s", url_label(url))

    def _prune_stale_urls(self, state: RepositoryState, active_urls: set[str]) -> None:
        for stale_url in set(state.url_ids) - active_urls:
            LOGGER.info("URL retirée de la surveillance: %s", url_label(stale_url))
            del state.url_ids[stale_url]
            self._failure_logs.pop(stale_url, None)
