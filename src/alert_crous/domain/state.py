from dataclasses import dataclass, field

from .models import Logement


@dataclass
class StoredLogement:
    logement: Logement
    message_id: str | None = None
    notification_status: str = "pending"
    available: bool = True
    miss_count: int = 0


@dataclass
class RepositoryState:
    logements: dict[str, StoredLogement] = field(default_factory=dict)
    url_ids: dict[str, set[str]] = field(default_factory=dict)
