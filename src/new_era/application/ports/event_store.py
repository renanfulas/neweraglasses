from __future__ import annotations

from typing import Protocol

from new_era.domain.events.models import Event


class EventStore(Protocol):
    def append(self, event: Event) -> None:
        raise NotImplementedError

    def list_events(
        self,
        *,
        session_id: str | None = None,
        trace_id: str | None = None,
    ) -> list[Event]:
        raise NotImplementedError
