from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping
from uuid import uuid4

from new_era.domain.events.redaction import validate_event_metadata


class EventType(StrEnum):
    OBSERVATION_CREATED = "observation_created"
    ALERT_CANDIDATE_CREATED = "alert_candidate_created"
    ALERT_SHOWN = "alert_shown"
    ALERT_SUPPRESSED = "alert_suppressed"
    ALERT_VIEWED = "alert_viewed"
    ALERT_DISMISSED = "alert_dismissed"
    ALERT_FEEDBACK_GIVEN = "alert_feedback_given"
    ATTENTION_BUDGET_EXCEEDED = "attention_budget_exceeded"
    USER_SETTING_CHANGED = "user_setting_changed"
    DOCUMENT_ANALYZED = "document_analyzed"
    SHOPPING_ITEM_DETECTED = "shopping_item_detected"
    JOB_STARTED = "job_started"
    JOB_STATUS_UPDATED = "job_status_updated"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    DOCUMENT_ANALYSIS_FEEDBACK_GIVEN = "document_analysis_feedback_given"
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_RETENTION_EXPIRED = "document_retention_expired"
    UPLOAD_REJECTED = "upload_rejected"
    FEEDBACK_METRIC_COMPUTED = "feedback_metric_computed"
    OCR_QUALITY_EVALUATED = "ocr_quality_evaluated"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    AI_CALL_COMPLETED = "ai_call_completed"
    AI_CALL_FAILED = "ai_call_failed"
    LENS_COMMAND_DELIVERED = "lens_command_delivered"
    DEVICE_CAPABILITY_MISSING = "device_capability_missing"
    DEVICE_DELIVERY_FAILED = "device_delivery_failed"


@dataclass(frozen=True, slots=True)
class Event:
    event_type: EventType
    user_id: str
    session_id: str
    module: str
    correlation_id: str
    trace_id: str
    metadata: Mapping[str, object] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex}")
    event_version: int = 1
    policy_version: str | None = None
    model_version: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        validate_event_metadata(self.metadata)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "event_version": self.event_version,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "module": self.module,
            "policy_version": self.policy_version,
            "model_version": self.model_version,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }
