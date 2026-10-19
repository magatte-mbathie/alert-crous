from alert_crous.adapters.persistence.sqlite_repository import SqliteLogementRepository
from alert_crous.domain.models import Logement
from alert_crous.domain.state import RepositoryState, StoredLogement


def build_logement(logement_id: str) -> Logement:
    return Logement(
        id=logement_id,
        title="Studio test",
        link=f"https://example.com/{logement_id}",
        price="350 €",
        address="1 rue de Test",
        surface="20 m²",
        occupation="Individuel",
        logement_type="STUDIO",
        image_url="https://example.com/image.jpg",
        detected_at=1700000000,
    )


def test_sqlite_repository_round_trip(tmp_path):
    repository = SqliteLogementRepository(tmp_path / "state.sqlite3")
    state = RepositoryState(
        logements={
            "a": StoredLogement(
                logement=build_logement("a"),
                message_id="msg-a",
                notification_status="sent",
                available=True,
                miss_count=0,
            ),
            "b": StoredLogement(
                logement=build_logement("b"),
                notification_status="ignored",
                available=False,
                miss_count=2,
            ),
        },
        url_ids={"https://example.com/search": {"a", "b"}},
    )

    repository.save_state(state)
    loaded = repository.load_state()

    assert set(loaded.logements) == {"a", "b"}
    assert loaded.logements["a"].message_id == "msg-a"
    assert loaded.logements["a"].logement == build_logement("a")
    assert loaded.logements["b"].notification_status == "ignored"
    assert loaded.logements["b"].available is False
    assert loaded.logements["b"].miss_count == 2
    assert loaded.url_ids == {"https://example.com/search": {"a", "b"}}


def test_sqlite_repository_replaces_previous_state(tmp_path):
    repository = SqliteLogementRepository(tmp_path / "state.sqlite3")
    repository.save_state(
        RepositoryState(
            logements={"a": StoredLogement(logement=build_logement("a"))},
            url_ids={"u": {"a"}},
        )
    )
    repository.save_state(
        RepositoryState(
            logements={"b": StoredLogement(logement=build_logement("b"))},
            url_ids={"u": {"b"}},
        )
    )

    loaded = repository.load_state()

    assert set(loaded.logements) == {"b"}
    assert loaded.url_ids == {"u": {"b"}}


def test_sqlite_repository_creates_parent_directory(tmp_path):
    database_path = tmp_path / "nested" / "directory" / "state.sqlite3"

    repository = SqliteLogementRepository(database_path)
    repository.save_state(RepositoryState())

    assert database_path.exists()
