from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from new_era.application.ports import EventStore
from new_era.domain.events import Event, EventType


class LensFeedbackValue(StrEnum):
    USEFUL = "useful"
    NOT_USEFUL = "not_useful"


@dataclass(frozen=True, slots=True)
class LensFeedbackResult:
    event_id: str
    command_id: str
    feedback: LensFeedbackValue


@dataclass(frozen=True, slots=True)
class RecordLensFeedback:
    event_store: EventStore

    def execute(
        self,
        *,
        command_id: str,
        user_id: str,
        session_id: str,
        feedback: LensFeedbackValue,
        correlation_id: str,
        trace_id: str | None = None,
    ) -> LensFeedbackResult | None:
        delivery_event = self._find_delivered_command(
            command_id=command_id,
            user_id=user_id,
            session_id=session_id,
        )
        if delivery_event is None:
            return None

        feedback_event = Event(
            event_type=EventType.ALERT_FEEDBACK_GIVEN,
            user_id=user_id,
            session_id=session_id,
            module=delivery_event.module,
            correlation_id=correlation_id,
            trace_id=trace_id or delivery_event.trace_id,
            metadata={
                "command_id": command_id,
                "feedback": feedback.value,
                "source": "pwa_companion",
            },
        )
        self.event_store.append(feedback_event)
        return LensFeedbackResult(
            event_id=feedback_event.event_id,
            command_id=command_id,
            feedback=feedback,
        )

    def _find_delivered_command(
        self,
        *,
        command_id: str,
        user_id: str,
        session_id: str,
    ) -> Event | None:
        for event in self.event_store.list_events(session_id=session_id):
            if event.user_id != user_id:
                continue
            if event.event_type != EventType.LENS_COMMAND_DELIVERED:
                continue
            if event.metadata.get("command_id") == command_id:
                return event
        return None
