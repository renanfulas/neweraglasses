from __future__ import annotations

from dataclasses import dataclass

from new_era.application.ports import EventStore
from new_era.domain.events import Event, EventType


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
    session_trace: tuple[SessionTraceEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "event_count": self.event_count,
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
    if event_type in (EventType.LENS_COMMAND_DELIVERED, EventType.DEVICE_CAPABILITY_MISSING):
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


@dataclass(frozen=True, slots=True)
class GetSessionTrace:
    event_store: EventStore

    def execute(
        self,
        *,
        session_id: str,
        trace_id: str | None = None,
    ) -> SessionTraceReadModel:
        events = self.event_store.list_events(session_id=session_id, trace_id=trace_id)
        entries = tuple(
            SessionTraceEntry(
                event_id=event.event_id,
                event_type=event.event_type.value,
                step=build_trace_step(event.event_type),
                title=build_trace_title(event),
                detail=build_trace_detail(event),
                created_at=event.created_at.isoformat(),
            )
            for event in events
        )
        return SessionTraceReadModel(
            session_id=session_id,
            trace_id=trace_id,
            event_count=len(entries),
            session_trace=entries,
        )
