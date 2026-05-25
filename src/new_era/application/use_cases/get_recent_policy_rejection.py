from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from new_era.application.ports import DocumentArtifactStore, EventStore, JobStore
from new_era.application.use_cases.policy_rejection import PolicyRejection
from new_era.domain.documents import DocumentArtifactStatus
from new_era.domain.events import EventType
from new_era.domain.jobs import JobStatus

RECENT_POLICY_REJECTION_WINDOW = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class GetRecentPolicyRejectionForSession:
    event_store: EventStore
    job_store: JobStore | None = None
    artifact_store: DocumentArtifactStore | None = None
    window: timedelta = RECENT_POLICY_REJECTION_WINDOW

    def execute(
        self,
        *,
        user_id: str,
        session_id: str,
        module: str = "documents",
    ) -> PolicyRejection | None:
        recent_events = self.event_store.list_events(
            user_id=user_id,
            session_id=session_id,
            module=module,
            event_types={
                EventType.UPLOAD_REJECTED,
                EventType.RATE_LIMIT_EXCEEDED,
                EventType.JOB_STARTED,
                EventType.DOCUMENT_UPLOADED,
            },
            created_after=datetime.now(UTC) - self.window,
            limit=50,
        )
        if not recent_events:
            return None

        rejection_events = [
            event
            for event in recent_events
            if event.event_type in {EventType.UPLOAD_REJECTED, EventType.RATE_LIMIT_EXCEEDED}
        ]
        if not rejection_events:
            return None

        event = rejection_events[-1]
        if any(
            later_event.event_type in {EventType.JOB_STARTED, EventType.DOCUMENT_UPLOADED}
            and later_event.created_at > event.created_at
            for later_event in recent_events
        ):
            return None
        metadata = dict(event.metadata)
        if event.event_type == EventType.RATE_LIMIT_EXCEEDED:
            rejection = self._build_rate_limit_rejection(metadata)
        else:
            rejection = self._build_upload_rejection(metadata)
        return rejection if self._is_still_relevant(
            rejection=rejection,
            user_id=user_id,
            session_id=session_id,
            module=module,
        ) else None

    def _build_rate_limit_rejection(self, metadata: dict[str, object]) -> PolicyRejection:
        error_code = str(metadata.get("error_code") or metadata.get("reason") or "rate_limit_exceeded")
        if error_code == "active_job_quota_exceeded":
            error_code = "session_active_job_limit_exceeded"
        if error_code == "session_active_job_limit_exceeded":
            message = "Wait for an analysis to finish before sending another document."
        elif error_code == "session_active_artifact_limit_exceeded":
            message = "This session reached the upload limit."
        elif error_code == "session_artifact_storage_limit_exceeded":
            message = "This session reached the local document storage limit."
        else:
            message = "This session reached a local document limit."
        return PolicyRejection(
            code=error_code,
            message=message,
            reason="quota_exceeded",
            scope=str(metadata.get("limit_scope") or "session"),
            limit=_as_int(metadata.get("limit_value")),
            current=_as_int(metadata.get("current_value")),
            retryable=True,
            metadata=metadata,
        )

    def _build_upload_rejection(self, metadata: dict[str, object]) -> PolicyRejection:
        error_code = str(metadata.get("error_code") or "upload_rejected")
        message_by_code = {
            "unsupported_upload_content_type": "Use PNG, JPEG, or WebP for document uploads.",
            "unsupported_camera_content_type": "Use PNG, JPEG, or WebP for camera contract review.",
            "upload_file_empty": "The selected file is empty.",
            "upload_payload_too_large": "The file is above the local upload limit.",
            "idempotency_payload_mismatch": "This retry does not match the original upload. Start a new upload.",
        }
        return PolicyRejection(
            code=error_code,
            message=message_by_code.get(error_code, "This upload was rejected by the local policy."),
            reason=str(metadata.get("reason") or "validation_failed"),
            scope=str(metadata.get("limit_scope") or metadata.get("scope") or "upload"),
            limit=_as_int(metadata.get("limit_value")),
            current=_as_int(metadata.get("current_value") or metadata.get("byte_size")),
            retryable=error_code != "idempotency_payload_mismatch",
            metadata=metadata,
        )

    def _is_still_relevant(
        self,
        *,
        rejection: PolicyRejection,
        user_id: str,
        session_id: str,
        module: str,
    ) -> bool:
        if rejection.code == "session_active_job_limit_exceeded" and self.job_store is not None:
            active_jobs = self.job_store.count_by_session_statuses(
                user_id=user_id,
                session_id=session_id,
                statuses=(JobStatus.QUEUED, JobStatus.RUNNING),
                module=module,
            )
            return rejection.limit is None or active_jobs >= rejection.limit

        if (
            rejection.code in {
                "session_active_artifact_limit_exceeded",
                "session_artifact_storage_limit_exceeded",
            }
            and self.artifact_store is not None
        ):
            active_artifacts = self.artifact_store.list_by_session(
                user_id=user_id,
                session_id=session_id,
                status=DocumentArtifactStatus.ACTIVE,
            )
            if rejection.code == "session_active_artifact_limit_exceeded":
                return rejection.limit is None or len(active_artifacts) >= rejection.limit
            active_total_bytes = sum(artifact.size_bytes for artifact in active_artifacts)
            return rejection.limit is None or active_total_bytes >= rejection.limit

        return True


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
