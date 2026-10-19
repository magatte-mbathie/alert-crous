from typing import Protocol

from .models import Logement
from .state import RepositoryState


class Scraper(Protocol):
    def fetch_logements(self, url: str) -> list[Logement]:
        ...


class Notifier(Protocol):
    def notify_logement(self, logement: Logement) -> str | None:
        ...

    def mark_unavailable(self, logement: Logement, message_id: str) -> bool:
        ...


class LogementRepository(Protocol):
    def load_state(self) -> RepositoryState:
        ...

    def save_state(self, state: RepositoryState) -> None:
        ...
