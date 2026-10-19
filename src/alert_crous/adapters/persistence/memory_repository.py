from copy import deepcopy

from ...domain.ports import LogementRepository
from ...domain.state import RepositoryState


class InMemoryLogementRepository(LogementRepository):
    def __init__(self, state: RepositoryState | None = None) -> None:
        self._state = deepcopy(state) if state is not None else RepositoryState()

    def load_state(self) -> RepositoryState:
        return deepcopy(self._state)

    def save_state(self, state: RepositoryState) -> None:
        self._state = deepcopy(state)
