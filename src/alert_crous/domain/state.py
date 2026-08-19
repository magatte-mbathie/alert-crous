from dataclasses import dataclass, field


@dataclass
class MonitorState:
    known_ids: set[str] = field(default_factory=set)