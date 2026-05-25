from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from uuid import uuid4

from new_era.application.ports.document_artifact_store import DocumentArtifactStore
from new_era.application.ports.local_document_artifact_storage import (
    LocalDocumentArtifactStorage,
)
from new_era.domain.documents import DocumentArtifactRecord, DocumentArtifactStatus


class DocumentArtifactError(Exception):
    pass


class DocumentArtifactNotFoundError(DocumentArtifactError):
    pass


class DocumentArtifactOwnershipError(DocumentArtifactError):
    pass


class DocumentArtifactQuotaExceededError(DocumentArtifactError):
    pass


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
            raise DocumentArtifactQuotaExceededError("session_active_artifact_limit_exceeded")

        if self.quota.max_total_bytes is not None:
            current_total_bytes = sum(artifact.size_bytes for artifact in active_artifacts)
            if current_total_bytes + incoming_size_bytes > self.quota.max_total_bytes:
                raise DocumentArtifactQuotaExceededError("session_artifact_storage_limit_exceeded")


@dataclass(frozen=True, slots=True)
class RegisterLocalDocumentArtifact:
    artifact_store: DocumentArtifactStore
    storage: LocalDocumentArtifactStorage
    quota_enforcer: EnforceSessionArtifactQuota | None = None

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
    ) -> DocumentArtifactRecord:
        if self.quota_enforcer is not None:
            self.quota_enforcer.execute(
                user_id=user_id,
                session_id=session_id,
                incoming_size_bytes=len(payload),
            )

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
        return persisted_record


@dataclass(frozen=True, slots=True)
class DeleteLocalDocumentArtifact:
    artifact_store: DocumentArtifactStore
    storage: LocalDocumentArtifactStorage

    def execute(
        self,
        *,
        artifact_id: str,
        user_id: str,
        session_id: str | None = None,
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

    def execute(
        self,
        *,
        artifact_id: str,
        user_id: str,
        session_id: str,
        expired_at: datetime | None = None,
    ) -> DocumentArtifactRecord:
        record = self.artifact_store.get(artifact_id)
        if record is None:
            raise DocumentArtifactNotFoundError("document_artifact_not_found")
        if record.user_id != user_id or record.session_id != session_id:
            raise DocumentArtifactOwnershipError("document_artifact_not_owned_by_session")
        if record.status != DocumentArtifactStatus.ACTIVE:
            return record
        effective_time = expired_at or datetime.now(UTC)
        updated_record = replace(
            record,
            status=DocumentArtifactStatus.EXPIRED,
            expires_at=effective_time,
            updated_at=effective_time,
        )
        self.artifact_store.update(updated_record)
        return updated_record
