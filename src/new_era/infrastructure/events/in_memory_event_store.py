from __future__ import annotations

from dataclasses import dataclass, field

from new_era.application.ports.event_store import EventStore
from new_era.domain.events.models import Event


@dataclass(slots=True)
class InMemoryEventStore(EventStore):
    events: list[Event] = field(default_factory=list)

    def append(self, event: Event) -> None:
        self.events.append(event)
