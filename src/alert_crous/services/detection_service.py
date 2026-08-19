import time
from dataclasses import replace

from ..domain.models import Logement


def detect_new_logements(logements: list[Logement], known_ids: set[str]) -> list[Logement]:
    now = int(time.time())
    return [replace(logement, detected_at=now) for logement in logements if logement.id not in known_ids]