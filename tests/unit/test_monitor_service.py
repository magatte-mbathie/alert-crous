from copy import deepcopy

from alert_crous.domain.models import Logement
from alert_crous.domain.state import RepositoryState, StoredLogement
from alert_crous.services.monitor_service import MonitorService


class FakeScraper:
    def __init__(self, results: dict[str, list[Logement] | Exception]) -> None:
        self.results = results
        self.calls: list[str] = []

    def fetch_logements(self, url: str) -> list[Logement]:
        self.calls.append(url)
        result = self.results.get(url, [])
        if isinstance(result, Exception):
            raise result
        return list(result)


class FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.unavailable: list[tuple[str, str]] = []
        self.fail_ids: set[str] = set()
        self.fail_unavailable_ids: set[str] = set()

    def notify_logement(self, logement: Logement) -> str | None:
        if logement.id in self.fail_ids:
            return None
        self.sent.append(logement.id)
        return f"msg-{logement.id}"

    def mark_unavailable(self, logement: Logement, message_id: str) -> bool:
        if logement.id in self.fail_unavailable_ids:
            return False
        self.unavailable.append((logement.id, message_id))
        return True


class ExplodingNotifier(FakeNotifier):
    def notify_logement(self, logement: Logement) -> str | None:
        raise RuntimeError("erreur inattendue")

    def mark_unavailable(self, logement: Logement, message_id: str) -> bool:
        raise RuntimeError("erreur inattendue")


class FakeRepository:
    def __init__(self, state: RepositoryState | None = None) -> None:
        self.state = deepcopy(state) if state is not None else RepositoryState()
        self.saved_states: list[RepositoryState] = []

    def load_state(self) -> RepositoryState:
        return deepcopy(self.state)

    def save_state(self, state: RepositoryState) -> None:
        self.state = deepcopy(state)
        self.saved_states.append(deepcopy(state))


def logement(logement_id: str, title: str = "Studio") -> Logement:
    return Logement(
        id=logement_id,
        title=title,
        link=f"https://example.com/{logement_id}",
        price="350 €",
        address="1 rue de Test",
        surface="20 m²",
        occupation="Individuel",
        logement_type="STUDIO",
    )


def build_service(
    results: dict[str, list[Logement] | Exception],
    state: RepositoryState | None = None,
    miss_threshold: int = 2,
) -> tuple[MonitorService, FakeScraper, FakeNotifier, FakeRepository]:
    scraper = FakeScraper(results)
    notifier = FakeNotifier()
    repository = FakeRepository(state)
    service = MonitorService(
        scraper,
        notifier,
        repository,
        miss_threshold=miss_threshold,
    )
    return service, scraper, notifier, repository


def test_first_scan_notifies_existing_logements_only_once():
    service, _, notifier, repository = build_service({"u": [logement("a"), logement("b")]})

    service.run_once(["u"], notify_existing=True)
    service.run_once(["u"], notify_existing=True)

    assert notifier.sent == ["a", "b"]
    assert set(repository.state.url_ids["u"]) == {"a", "b"}
    assert all(stored.notification_status == "sent" for stored in repository.state.logements.values())


def test_first_scan_can_ignore_existing_logements():
    scraper = FakeScraper({"u": [logement("a"), logement("b")]})
    notifier = FakeNotifier()
    repository = FakeRepository()
    service = MonitorService(scraper, notifier, repository)

    service.run_once(["u"], notify_existing=False)
    scraper.results["u"] = [logement("a"), logement("b"), logement("c")]
    service.run_once(["u"], notify_existing=False)

    assert notifier.sent == ["c"]


def test_new_logement_is_notified_once():
    scraper = FakeScraper({"u": [logement("a")]})
    notifier = FakeNotifier()
    repository = FakeRepository()
    service = MonitorService(scraper, notifier, repository)

    service.run_once(["u"])
    service.run_once(["u"])
    scraper.results["u"] = [logement("a"), logement("b")]
    service.run_once(["u"])
    service.run_once(["u"])

    assert notifier.sent == ["a", "b"]


def test_removed_logement_is_marked_unavailable_after_threshold():
    scraper = FakeScraper({"u": [logement("a"), logement("b")]})
    notifier = FakeNotifier()
    repository = FakeRepository()
    service = MonitorService(scraper, notifier, repository, miss_threshold=2)

    service.run_once(["u"])
    scraper.results["u"] = [logement("b")]
    service.run_once(["u"])
    assert notifier.unavailable == []

    service.run_once(["u"])
    assert notifier.unavailable == [("a", "msg-a")]
    assert repository.state.logements["a"].available is False
    assert repository.state.logements["b"].available is True


def test_notification_failure_is_retried_without_duplicate():
    scraper = FakeScraper({"u": [logement("a")]})
    notifier = FakeNotifier()
    notifier.fail_ids = {"a"}
    repository = FakeRepository()
    service = MonitorService(scraper, notifier, repository)

    service.run_once(["u"])
    assert notifier.sent == []
    assert repository.state.logements["a"].notification_status == "pending"

    notifier.fail_ids.clear()
    service.run_once(["u"])
    service.run_once(["u"])

    assert notifier.sent == ["a"]
    assert repository.state.logements["a"].notification_status == "sent"


def test_failed_url_does_not_mark_its_logements_unavailable():
    scraper = FakeScraper({"u1": [logement("a")], "u2": [logement("b")]})
    notifier = FakeNotifier()
    repository = FakeRepository()
    service = MonitorService(scraper, notifier, repository, miss_threshold=1)

    service.run_once(["u1", "u2"])
    scraper.results["u2"] = RuntimeError("CROUS indisponible")
    service.run_once(["u1", "u2"])
    service.run_once(["u1", "u2"])

    assert notifier.unavailable == []
    assert repository.state.logements["b"].available is True
    assert repository.state.url_ids["u2"] == {"b"}


def test_all_urls_failing_keeps_state_unchanged():
    scraper = FakeScraper({"u": [logement("a")]})
    notifier = FakeNotifier()
    repository = FakeRepository()
    service = MonitorService(scraper, notifier, repository, miss_threshold=1)

    service.run_once(["u"])
    screenshot = deepcopy(repository.state)
    scraper.results["u"] = RuntimeError("panne")
    service.run_once(["u"])

    assert repository.state == screenshot
    assert notifier.unavailable == []


def test_mark_unavailable_failure_is_retried():
    scraper = FakeScraper({"u": [logement("a")]})
    notifier = FakeNotifier()
    notifier.fail_unavailable_ids = {"a"}
    repository = FakeRepository()
    service = MonitorService(scraper, notifier, repository, miss_threshold=1)

    service.run_once(["u"])
    scraper.results["u"] = []
    service.run_once(["u"])
    assert repository.state.logements["a"].available is True
    assert notifier.unavailable == []

    notifier.fail_unavailable_ids.clear()
    service.run_once(["u"])
    assert notifier.unavailable == [("a", "msg-a")]
    assert repository.state.logements["a"].available is False


def test_reappearing_logement_is_notified_again():
    scraper = FakeScraper({"u": [logement("a")]})
    notifier = FakeNotifier()
    repository = FakeRepository()
    service = MonitorService(scraper, notifier, repository, miss_threshold=1)

    service.run_once(["u"])
    scraper.results["u"] = []
    service.run_once(["u"])
    assert repository.state.logements["a"].available is False

    scraper.results["u"] = [logement("a")]
    service.run_once(["u"])

    assert notifier.sent == ["a", "a"]
    assert repository.state.logements["a"].available is True


def test_pending_logement_disappearing_is_marked_unavailable_without_message():
    scraper = FakeScraper({"u": [logement("a")]})
    notifier = FakeNotifier()
    notifier.fail_ids = {"a"}
    repository = FakeRepository()
    service = MonitorService(scraper, notifier, repository, miss_threshold=1)

    service.run_once(["u"])
    scraper.results["u"] = []
    service.run_once(["u"])

    assert notifier.unavailable == []
    assert repository.state.logements["a"].available is False


def test_stale_url_state_is_pruned():
    state = RepositoryState(
        logements={
            "a": StoredLogement(
                logement=logement("a"),
                message_id="msg-a",
                notification_status="sent",
            )
        },
        url_ids={"old": {"a"}},
    )
    service, _, notifier, repository = build_service({"new": []}, state=state, miss_threshold=1)

    service.run_once(["new"])

    assert "old" not in repository.state.url_ids
    assert repository.state.logements["a"].available is False
    assert notifier.unavailable == [("a", "msg-a")]


def test_state_persists_across_service_restart(tmp_path):
    from alert_crous.adapters.persistence.sqlite_repository import SqliteLogementRepository

    database_path = tmp_path / "state.sqlite3"
    scraper = FakeScraper({"u": [logement("a")]})
    first_notifier = FakeNotifier()
    first_service = MonitorService(
        scraper,
        first_notifier,
        SqliteLogementRepository(database_path),
    )
    first_service.run_once(["u"])

    second_notifier = FakeNotifier()
    second_service = MonitorService(
        scraper,
        second_notifier,
        SqliteLogementRepository(database_path),
    )
    second_service.run_once(["u"])

    assert first_notifier.sent == ["a"]
    assert second_notifier.sent == []


def test_pending_notification_is_retried_after_restart(tmp_path):
    from alert_crous.adapters.persistence.sqlite_repository import SqliteLogementRepository

    database_path = tmp_path / "state.sqlite3"
    scraper = FakeScraper({"u": [logement("a")]})
    first_notifier = FakeNotifier()
    first_notifier.fail_ids = {"a"}
    first_service = MonitorService(
        scraper,
        first_notifier,
        SqliteLogementRepository(database_path),
    )
    first_service.run_once(["u"])

    second_notifier = FakeNotifier()
    second_service = MonitorService(
        scraper,
        second_notifier,
        SqliteLogementRepository(database_path),
    )
    second_service.run_once(["u"])

    assert second_notifier.sent == ["a"]


def test_unexpected_notifier_exception_is_treated_as_pending():
    scraper = FakeScraper({"u": [logement("a")]})
    notifier = ExplodingNotifier()
    repository = FakeRepository()
    service = MonitorService(scraper, notifier, repository)

    service.run_once(["u"])

    assert repository.state.logements["a"].notification_status == "pending"
    assert repository.state.logements["a"].available is True

    retry_notifier = FakeNotifier()
    retry_service = MonitorService(scraper, retry_notifier, repository)
    retry_service.run_once(["u"])

    assert retry_notifier.sent == ["a"]


def test_unexpected_mark_unavailable_exception_is_retried():
    scraper = FakeScraper({"u": [logement("a")]})
    repository = FakeRepository()
    first_service = MonitorService(
        scraper,
        FakeNotifier(),
        repository,
        miss_threshold=1,
    )
    first_service.run_once(["u"])

    scraper.results["u"] = []
    exploding_service = MonitorService(
        scraper,
        ExplodingNotifier(),
        repository,
        miss_threshold=1,
    )
    exploding_service.run_once(["u"])

    assert repository.state.logements["a"].available is True

    retry_notifier = FakeNotifier()
    retry_service = MonitorService(
        scraper,
        retry_notifier,
        repository,
        miss_threshold=1,
    )
    retry_service.run_once(["u"])

    assert retry_notifier.unavailable == [("a", "msg-a")]
    assert repository.state.logements["a"].available is False
