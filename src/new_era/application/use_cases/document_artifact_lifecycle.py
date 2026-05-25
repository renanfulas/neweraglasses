from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from uuid import uuid4

from new_era.application.ports.document_artifact_store import DocumentArtifactStore
from new_era.application.ports.event_store import EventStore
from new_era.application.ports.local_document_artifact_storage import (
    LocalDocumentArtifactStorage,
)
from new_era.domain.documents import DocumentArtifactRecord, DocumentArtifactStatus
from new_era.domain.events import Event, EventType


class DocumentArtifactError(Exception):
    pass


class DocumentArtifactNotFoundError(DocumentArtifactError):
    pass


class DocumentArtifactOwnershipError(DocumentArtifactError):
    pass


class DocumentArtifactQuotaExceededError(DocumentArtifactError):
    def __init__(
        self,
        code: str,
        *,
        limit: int | None = None,
        current: int | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.limit = limit
        self.current = current


@dataclass(frozen=True, slots=True)
class SessionArtifactQuota:
    max_active_artifacts: int | None = None
    max_total_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class EnforceSessionArtifactQuota:
    artifact_store: DocumentArtifactStore
    quota: SessionArtifactQuota = field(default_factory=SessionArtifactQuota)

    def execute(
        self,
        *,
        user_id: str,
        session_id: str,
        incoming_size_bytes: int,
    ) -> None:
        active_artifacts = self.artifact_store.list_by_session(
            user_id=user_id,
            session_id=session_id,
            status=DocumentArtifactStatus.ACTIVE,
        )
        if (
            self.quota.max_active_artifacts is not None
            and len(active_artifacts) >= self.quota.max_active_artifacts
        ):
            raise DocumentArtifactQuotaExceededError(
                "session_active_artifact_limit_exceeded",
                limit=self.quota.max_active_artifacts,
                current=len(active_artifacts),
            )

        if self.quota.max_total_bytes is not None:
            current_total_bytes = sum(artifact.size_bytes for artifact in active_artifacts)
            if current_total_bytes + incoming_size_bytes > self.quota.max_total_bytes:
                raise DocumentArtifactQuotaExceededError(
                    "session_artifact_storage_limit_exceeded",
                    limit=self.quota.max_total_bytes,
                    current=current_total_bytes + incoming_size_bytes,
                )


@dataclass(frozen=True, slots=True)
class RegisterLocalDocumentArtifact:
    artifact_store: DocumentArtifactStore
    storage: LocalDocumentArtifactStorage
    quota_enforcer: EnforceSessionArtifactQuota | None = None
    event_store: EventStore | None = None

    def execute(
        self,
        *,
        user_id: str,
        session_id: str,
        artifact_label: str,
        source_type: str,
        content_type: str,
        payload: bytes,
        artifact_id: str | None = None,
        expires_at: datetime | None = None,
        metadata: dict[str, object] | None = None,
        correlation_id: str | None = None,
        trace_id: str | None = None,
    ) -> DocumentArtifactRecord:
        if self.quota_enforcer is not None:
            try:
                self.quota_enforcer.execute(
                    user_id=user_id,
                    session_id=session_id,
                    incoming_size_bytes=len(payload),
                )
            except DocumentArtifactQuotaExceededError as exc:
                self._append_quota_rejection_event(
                    user_id=user_id,
                    session_id=session_id,
                    source_type=source_type,
                    content_type=content_type,
                    payload_size_bytes=len(payload),
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    error=exc,
                )
                raise

        record = DocumentArtifactRecord(
            artifact_id=artifact_id or f"artifact_{uuid4().hex}",
            user_id=user_id,
            session_id=session_id,
            artifact_label=artifact_label,
            source_type=source_type,
            content_type=content_type,
            size_bytes=len(payload),
            storage_key="pending",
            local_path="pending",
            expires_at=expires_at,
            metadata=metadata or {},
        )

        stored_artifact = self.storage.save(
            artifact_id=record.artifact_id,
            session_id=session_id,
            artifact_label=artifact_label,
            payload=payload,
        )
        persisted_record = replace(
            record,
            storage_key=stored_artifact.storage_key,
            local_path=stored_artifact.local_path,
            size_bytes=stored_artifact.size_bytes,
        )
        try:
            self.artifact_store.save(persisted_record)
        except Exception:
            self.storage.delete(storage_key=stored_artifact.storage_key)
            raise
        self._append_lifecycle_event(
            record=persisted_record,
            event_type=EventType.DOCUMENT_UPLOADED,
            correlation_id=correlation_id,
            trace_id=trace_id,
            metadata={
                "content_type": persisted_record.content_type,
                "size_bytes": persisted_record.size_bytes,
                "status": persisted_record.status.value,
                "source_type": persisted_record.source_type,
            },
        )
        return persisted_record

    def _append_lifecycle_event(
        self,
        *,
        record: DocumentArtifactRecord,
        event_type: EventType,
        correlation_id: str | None,
        trace_id: str | None,
        metadata: dict[str, object],
    ) -> None:
        if self.event_store is None:
            return
        self.event_store.append(
            Event(
                event_type=event_type,
                user_id=record.user_id,
                session_id=record.session_id,
                module="documents",
                correlation_id=correlation_id or f"corr_{uuid4().hex}",
                trace_id=trace_id or f"trace_{uuid4().hex}",
                metadata={
                    "artifact_id": record.artifact_id,
                    **metadata,
                },
            )
        )

    def _append_quota_rejection_event(
        self,
        *,
        user_id: str,
        session_id: str,
        source_type: str,
        content_type: str,
        payload_size_bytes: int,
        correlation_id: str | None,
        trace_id: str | None,
        error: DocumentArtifactQuotaExceededError,
    ) -> None:
        if self.event_store is None:
            return
        self.event_store.append(
            Event(
                event_type=EventType.RATE_LIMIT_EXCEEDED,
                user_id=user_id,
                session_id=session_id,
                module="documents",
                correlation_id=correlation_id or f"corr_{uuid4().hex}",
                trace_id=trace_id or f"trace_{uuid4().hex}",
                metadata={
                    "reason": "artifact_quota_exceeded",
                    "error_code": error.code,
                    "limit_scope": "session",
                    "limit_value": error.limit,
                    "current_value": error.current,
                    "byte_size": payload_size_bytes,
                    "content_type": content_type,
                    "source_type": source_type,
                },
            )
        )


@dataclass(frozen=True, slots=True)
class DeleteLocalDocumentArtifact:
    artifact_store: DocumentArtifactStore
    storage: LocalDocumentArtifactStorage
    event_store: EventStore | None = None

    def execute(
        self,
        *,
        artifact_id: str,
        user_id: str,
        session_id: str | None = None,
        correlation_id: str | None = None,
        trace_id: str | None = None,
    ) -> DocumentArtifactRecord:
        record = self._get_owned_record(
            artifact_id=artifact_id,
            user_id=user_id,
            session_id=session_id,
        )
        if record.status == DocumentArtifactStatus.DELETED:
            return record

        self.storage.delete(storage_key=record.storage_key)
        deleted_at = datetime.now(UTC)
        updated_record = replace(
            record,
            status=DocumentArtifactStatus.DELETED,
            deleted_at=deleted_at,
            updated_at=deleted_at,
        )
        self.artifact_store.update(updated_record)
        if self.event_store is not None:
            self.event_store.append(
                Event(
                    event_type=EventType.DOCUMENT_DELETED,
                    user_id=updated_record.user_id,
                    session_id=updated_record.session_id,
                    module="documents",
                    correlation_id=correlation_id or f"corr_{uuid4().hex}",
                    trace_id=trace_id or f"trace_{uuid4().hex}",
                    metadata={
                        "artifact_id": updated_record.artifact_id,
                        "content_type": updated_record.content_type,
                        "deleted_at": deleted_at.isoformat(),
                        "size_bytes": updated_record.size_bytes,
                        "source_type": updated_record.source_type,
                        "status": updated_record.status.value,
                    },
                )
            )
        return updated_record

    def _get_owned_record(
        self,
        *,
        artifact_id: str,
        user_id: str,
        session_id: str | None,
    ) -> DocumentArtifactRecord:
        record = self.artifact_store.get(artifact_id)
        if record is None:
            raise DocumentArtifactNotFoundError("document_artifact_not_found")
        if record.user_id != user_id or (
            session_id is not None and record.session_id != session_id
        ):
            raise DocumentArtifactOwnershipError("document_artifact_not_owned_by_session")
        return record


@dataclass(frozen=True, slots=True)
class ExpireDocumentArtifact:
    artifact_store: DocumentArtifactStore
    storage: LocalDocumentArtifactStorage | None = None
    event_store: EventStore | None = None

    def execute(
        self,
        *,
        artifact_id: str,
        user_id: str,
        session_id: str,
        expired_at: datetime | None = None,
        correlation_id: str | None = None,
        trace_id: str | None = None,
    ) -> DocumentArtifactRecord:
        record = self.artifact_store.get(artifact_id)
        if record is None:
            raise DocumentArtifactNotFoundError("document_artifact_not_found")
        if record.user_id != user_id or record.session_id != session_id:
            raise DocumentArtifactOwnershipError("document_artifact_not_owned_by_session")
        if record.status != DocumentArtifactStatus.ACTIVE:
            return record
        effective_time = expired_at or datetime.now(UTC)
        if self.storage is not None:
            self.storage.delete(storage_key=record.storage_key)
        updated_record = replace(
            record,
            status=DocumentArtifactStatus.EXPIRED,
            expires_at=effective_time,
            updated_at=effective_time,
        )
        self.artifact_store.update(updated_record)
        if self.event_store is not None:
            self.event_store.append(
                Event(
                    event_type=EventType.DOCUMENT_RETENTION_EXPIRED,
                    user_id=updated_record.user_id,
                    session_id=updated_record.session_id,
                    module="documents",
                    correlation_id=correlation_id or f"corr_{uuid4().hex}",
                    trace_id=trace_id or f"trace_{uuid4().hex}",
                    metadata={
                        "artifact_id": updated_record.artifact_id,
                        "content_type": updated_record.content_type,
                        "expired_at": effective_time.isoformat(),
                        "size_bytes": updated_record.size_bytes,
                        "source_type": updated_record.source_type,
                        "status": updated_record.status.value,
                    },
                )
            )
        return updated_record
