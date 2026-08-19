from ...domain.ports import LogementRepository


class InMemoryLogementRepository(LogementRepository):
    def __init__(self) -> None:
        self._known_ids: set[str] = set()

    def get_known_ids(self) -> set[str]:
        return set(self._known_ids)

    def save_seen_ids(self, ids: set[str]) -> None:
        self._known_ids = set(ids)