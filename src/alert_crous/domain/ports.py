from typing import Protocol

from .models import Logement


class Scraper(Protocol):
    def fetch_logements(self, url: str) -> list[Logement]:
        ...


class Notifier(Protocol):
    def notify_new_logements(self, logements: list[Logement]) -> None:
        ...

    def mark_unavailable_logements(self, logement_ids: set[str]) -> None:
        ...


class LogementRepository(Protocol):
    def get_known_ids(self) -> set[str]:
        ...

    def save_seen_ids(self, ids: set[str]) -> None:
        ...