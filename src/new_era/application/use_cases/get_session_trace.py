from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime

from new_era.application.ports import EventStore
from new_era.domain.events import Event, EventType

DEFAULT_TRACE_LIMIT = 50
MAX_TRACE_LIMIT = 100


@dataclass(frozen=True, slots=True)
class SessionTraceEntry:
    event_id: str
    event_type: str
    step: str
    title: str
    detail: str
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "step": self.step,
            "title": self.title,
            "detail": self.detail,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class SessionTraceReadModel:
    session_id: str
    trace_id: str | None
    event_count: int
    next_cursor: str | None
    session_trace: tuple[SessionTraceEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "event_count": self.event_count,
            "next_cursor": self.next_cursor,
            "session_trace": [entry.to_dict() for entry in self.session_trace],
        }


def build_trace_title(event: Event) -> str:
    if event.event_type == EventType.OBSERVATION_CREATED:
        return "Observation captured"
    if event.event_type == EventType.ALERT_CANDIDATE_CREATED:
        return "Alert candidate created"
    if event.event_type == EventType.ALERT_SHOWN:
        return "Attention policy allowed display"
    if event.event_type == EventType.ALERT_SUPPRESSED:
        return "Attention policy suppressed alert"
    if event.event_type == EventType.LENS_COMMAND_DELIVERED:
        return "Lens command delivered"
    if event.event_type == EventType.DEVICE_CAPABILITY_MISSING:
        return "Device capability missing"
    if event.event_type == EventType.DEVICE_DELIVERY_FAILED:
        return "Device delivery failed"
    if event.event_type == EventType.JOB_STARTED:
        return "Document analysis job accepted"
    if event.event_type == EventType.JOB_STATUS_UPDATED:
        return "Document analysis job updated"
    if event.event_type == EventType.JOB_COMPLETED:
        return "Document analysis job completed"
    if event.event_type == EventType.JOB_FAILED:
        return "Document analysis job failed"
    if event.event_type == EventType.AI_CALL_FAILED:
        return "Document analysis attempt failed"
    if event.event_type == EventType.ALERT_FEEDBACK_GIVEN:
        return "Lens feedback recorded"
    return event.event_type.value.replace("_", " ").title()


def build_trace_detail(event: Event) -> str:
    metadata = event.metadata
    if event.event_type == EventType.OBSERVATION_CREATED:
        return str(metadata.get("summary", "Observation received."))
    if event.event_type == EventType.ALERT_CANDIDATE_CREATED:
        priority = str(metadata.get("priority", "unknown")).replace("_", " ")
        confidence = metadata.get("confidence")
        return (
            f"{metadata.get('alert_type', 'alert')} candidate "
            f"with {priority} priority at confidence {confidence}."
        )
    if event.event_type in (EventType.ALERT_SHOWN, EventType.ALERT_SUPPRESSED):
        return str(metadata.get("reason", "No decision reason recorded."))
    if event.event_type == EventType.LENS_COMMAND_DELIVERED:
        return f"Rendered by {metadata.get('adapter_name', 'device adapter')}."
    if event.event_type == EventType.DEVICE_CAPABILITY_MISSING:
        return (
            f"Missing {metadata.get('missing_capability', 'required capability')} on "
            f"{metadata.get('adapter_name', 'device adapter')}."
        )
    if event.event_type == EventType.DEVICE_DELIVERY_FAILED:
        return f"Delivery failed on {metadata.get('adapter_name', 'device adapter')}."
    if event.event_type == EventType.JOB_STARTED:
        return (
            f"Queued {metadata.get('job_type', 'job')} for "
            f"{metadata.get('artifact_label', 'document artifact')}."
        )
    if event.event_type == EventType.JOB_STATUS_UPDATED:
        return (
            f"Moved job from {metadata.get('from_status', 'unknown')} "
            f"to {metadata.get('to_status', 'unknown')}."
        )
    if event.event_type == EventType.JOB_COMPLETED:
        return f"Completed {metadata.get('job_type', 'job')}."
    if event.event_type == EventType.JOB_FAILED:
        return f"Failed {metadata.get('job_type', 'job')}."
    if event.event_type == EventType.AI_CALL_FAILED:
        retry_text = "retry scheduled" if metadata.get("retry_scheduled") else "no retry"
        return f"Attempt {metadata.get('attempt', 'unknown')} failed; {retry_text}."
    if event.event_type == EventType.ALERT_FEEDBACK_GIVEN:
        feedback = str(metadata.get("feedback", "feedback")).replace("_", " ")
        return f"Marked the lens alert as {feedback}."
    return "Event recorded."


def build_trace_step(event_type: EventType) -> str:
    if event_type == EventType.OBSERVATION_CREATED:
        return "observation"
    if event_type == EventType.ALERT_CANDIDATE_CREATED:
        return "candidate"
    if event_type in (EventType.ALERT_SHOWN, EventType.ALERT_SUPPRESSED):
        return "decision"
    if event_type in (
        EventType.LENS_COMMAND_DELIVERED,
        EventType.DEVICE_CAPABILITY_MISSING,
        EventType.DEVICE_DELIVERY_FAILED,
    ):
        return "delivery"
    if event_type in (
        EventType.JOB_STARTED,
        EventType.JOB_STATUS_UPDATED,
        EventType.JOB_COMPLETED,
        EventType.JOB_FAILED,
    ):
        return "job"
    if event_type == EventType.AI_CALL_FAILED:
        return "provider"
    if event_type == EventType.ALERT_FEEDBACK_GIVEN:
        return "feedback"
    return "system"


TRACE_STEP_EVENT_TYPES: dict[str, set[EventType]] = {
    "observation": {EventType.OBSERVATION_CREATED},
    "candidate": {EventType.ALERT_CANDIDATE_CREATED},
    "decision": {EventType.ALERT_SHOWN, EventType.ALERT_SUPPRESSED},
    "delivery": {
        EventType.LENS_COMMAND_DELIVERED,
        EventType.DEVICE_CAPABILITY_MISSING,
        EventType.DEVICE_DELIVERY_FAILED,
    },
    "job": {
        EventType.JOB_STARTED,
        EventType.JOB_STATUS_UPDATED,
        EventType.JOB_COMPLETED,
        EventType.JOB_FAILED,
    },
    "provider": {EventType.AI_CALL_FAILED},
    "feedback": {EventType.ALERT_FEEDBACK_GIVEN},
}


def normalize_trace_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_TRACE_LIMIT
    if limit < 1:
        raise ValueError("limit must be at least 1")
    return min(limit, MAX_TRACE_LIMIT)


def encode_trace_cursor(event: Event) -> str:
    value = f"{event.created_at.isoformat()}|{event.event_id}"
    return urlsafe_b64encode(value.encode("utf-8")).decode("ascii")


def decode_trace_cursor(cursor: str | None) -> tuple[datetime, str] | None:
    if cursor is None:
        return None
    try:
        decoded = urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        created_at_text, event_id = decoded.split("|", 1)
        return datetime.fromisoformat(created_at_text), event_id
    except Exception as exc:
        raise ValueError("invalid trace cursor") from exc


def event_types_for_steps(steps: set[str] | None) -> set[EventType] | None:
    if not steps:
        return None
    unknown_steps = steps.difference(TRACE_STEP_EVENT_TYPES.keys())
    if unknown_steps:
        names = ", ".join(sorted(unknown_steps))
        raise ValueError(f"unknown trace step filter: {names}")

    event_types: set[EventType] = set()
    for step in steps:
        event_types.update(TRACE_STEP_EVENT_TYPES[step])
    return event_types


def combine_event_type_filters(
    *,
    event_types: set[EventType] | None,
    steps: set[str] | None,
) -> set[EventType] | None:
    step_event_types = event_types_for_steps(steps)
    if event_types is None:
        return step_event_types
    if step_event_types is None:
        return event_types
    return event_types.intersection(step_event_types)


@dataclass(frozen=True, slots=True)
class GetSessionTrace:
    event_store: EventStore

    def execute(
        self,
        *,
        session_id: str,
        user_id: str | None = None,
        trace_id: str | None = None,
        module: str | None = None,
        event_types: set[EventType] | None = None,
        steps: set[str] | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> SessionTraceReadModel:
        normalized_limit = normalize_trace_limit(limit)
        combined_event_types = combine_event_type_filters(
            event_types=event_types,
            steps=steps,
        )
        events = self.event_store.list_events(
            user_id=user_id,
            session_id=session_id,
            trace_id=trace_id,
            module=module,
            event_types=combined_event_types,
            created_after=created_after,
            created_before=created_before,
            after=decode_trace_cursor(cursor),
            limit=normalized_limit + 1,
        )
        has_more = len(events) > normalized_limit
        page_events = events[:normalized_limit]
        entries = tuple(
            SessionTraceEntry(
                event_id=event.event_id,
                event_type=event.event_type.value,
                step=build_trace_step(event.event_type),
                title=build_trace_title(event),
                detail=build_trace_detail(event),
                created_at=event.created_at.isoformat(),
            )
            for event in page_events
        )
        return SessionTraceReadModel(
            session_id=session_id,
            trace_id=trace_id,
            event_count=len(entries),
            next_cursor=encode_trace_cursor(page_events[-1])
            if has_more and page_events
            else None,
            session_trace=entries,
        )
