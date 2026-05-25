from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class EventType(StrEnum):
    OBSERVATION_CREATED = "observation_created"
    ALERT_CANDIDATE_CREATED = "alert_candidate_created"
    ALERT_SHOWN = "alert_shown"
    ALERT_SUPPRESSED = "alert_suppressed"
    LENS_COMMAND_DELIVERED = "lens_command_delivered"
    DEVICE_CAPABILITY_MISSING = "device_capability_missing"
    DEVICE_DELIVERY_FAILED = "device_delivery_failed"
    JOB_STARTED = "job_started"
    JOB_STATUS_UPDATED = "job_status_updated"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    AI_CALL_FAILED = "ai_call_failed"
    ALERT_FEEDBACK_GIVEN = "alert_feedback_given"


@dataclass(frozen=True, slots=True)
class Event:
    event_type: EventType
    user_id: str
    session_id: str
    module: str
    correlation_id: str
    trace_id: str | None = None
    event_version: int = 1
    policy_version: str | None = None
    model_version: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: f"event_{uuid4().hex}")
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
