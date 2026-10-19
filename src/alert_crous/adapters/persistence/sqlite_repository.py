import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ...domain.models import Logement
from ...domain.ports import LogementRepository
from ...domain.state import RepositoryState, StoredLogement

SCHEMA = """
CREATE TABLE IF NOT EXISTS logements (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    link TEXT NOT NULL,
    price TEXT NOT NULL,
    address TEXT NOT NULL,
    surface TEXT NOT NULL,
    occupation TEXT NOT NULL,
    logement_type TEXT NOT NULL,
    image_url TEXT NOT NULL,
    detected_at INTEGER,
    message_id TEXT,
    notification_status TEXT NOT NULL,
    available INTEGER NOT NULL,
    miss_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS url_state (
    url TEXT NOT NULL,
    logement_id TEXT NOT NULL,
    PRIMARY KEY (url, logement_id)
);
"""


class SqliteLogementRepository(LogementRepository):
    """Persiste l'état de surveillance dans un fichier SQLite local."""

    def __init__(self, database_path: str | Path) -> None:
        raw_path = str(database_path)
        if raw_path == ":memory:":
            raise ValueError(
                "SQLite en mémoire n'est pas supporté; utilisez un fichier temporaire"
            )
        self.database_path = str(Path(raw_path).expanduser())
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=5)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def load_state(self) -> RepositoryState:
        state = RepositoryState()

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, link, price, address, surface, occupation,
                       logement_type, image_url, detected_at, message_id,
                       notification_status, available, miss_count
                FROM logements
                """
            ).fetchall()
            for row in rows:
                logement = Logement(
                    id=row[0],
                    title=row[1],
                    link=row[2],
                    price=row[3],
                    address=row[4],
                    surface=row[5],
                    occupation=row[6],
                    logement_type=row[7],
                    image_url=row[8],
                    detected_at=row[9],
                )
                state.logements[logement.id] = StoredLogement(
                    logement=logement,
                    message_id=row[10],
                    notification_status=row[11],
                    available=bool(row[12]),
                    miss_count=row[13],
                )

            for url, logement_id in connection.execute(
                "SELECT url, logement_id FROM url_state"
            ).fetchall():
                state.url_ids.setdefault(url, set()).add(logement_id)

        return state

    def save_state(self, state: RepositoryState) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM logements")
            connection.execute("DELETE FROM url_state")

            connection.executemany(
                """
                INSERT INTO logements (
                    id, title, link, price, address, surface, occupation,
                    logement_type, image_url, detected_at, message_id,
                    notification_status, available, miss_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        stored.logement.id,
                        stored.logement.title,
                        stored.logement.link,
                        stored.logement.price,
                        stored.logement.address,
                        stored.logement.surface,
                        stored.logement.occupation,
                        stored.logement.logement_type,
                        stored.logement.image_url,
                        stored.logement.detected_at,
                        stored.message_id,
                        stored.notification_status,
                        int(stored.available),
                        stored.miss_count,
                    )
                    for stored in state.logements.values()
                ],
            )

            connection.executemany(
                "INSERT INTO url_state (url, logement_id) VALUES (?, ?)",
                [
                    (url, logement_id)
                    for url, ids in state.url_ids.items()
                    for logement_id in ids
                ],
            )
