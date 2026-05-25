from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from new_era.application.use_cases.document_artifact_lifecycle import (
    DeleteLocalDocumentArtifact,
    DocumentArtifactOwnershipError,
    DocumentArtifactQuotaExceededError,
    EnforceSessionArtifactQuota,
    ExpireDocumentArtifact,
    RegisterLocalDocumentArtifact,
    SessionArtifactQuota,
)
from new_era.domain.documents import DocumentArtifactRecord, DocumentArtifactStatus
from new_era.domain.events import EventType
from new_era.infrastructure.documents.filesystem_document_artifact_storage import (
    FilesystemDocumentArtifactStorage,
)
from new_era.infrastructure.events import InMemoryEventStore
from new_era.infrastructure.documents.in_memory_document_artifact_store import (
    InMemoryDocumentArtifactStore,
)


class DocumentArtifactLifecycleUseCasesTest(TestCase):
    def test_registers_local_document_artifact(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = InMemoryDocumentArtifactStore()
            storage = FilesystemDocumentArtifactStorage(Path(temp_dir) / "uploads")
            event_store = InMemoryEventStore()
            use_case = RegisterLocalDocumentArtifact(
                artifact_store=store,
                storage=storage,
                event_store=event_store,
            )

            record = use_case.execute(
                user_id="user_1",
                session_id="session_1",
                artifact_label="contract page 1.png",
                source_type="pwa_multipart_upload",
                content_type="image/png",
                payload=b"binary-payload",
                metadata={"capture": "camera"},
            )

            persisted = store.get(record.artifact_id)
            self.assertEqual(persisted.size_bytes, len(b"binary-payload"))
            self.assertTrue(Path(persisted.local_path).exists())
            self.assertEqual(persisted.metadata["capture"], "camera")
            self.assertEqual(event_store.events[-1].event_type, EventType.DOCUMENT_UPLOADED)
            self.assertEqual(
                event_store.events[-1].metadata,
                {
                    "artifact_id": record.artifact_id,
                    "content_type": "image/png",
                    "size_bytes": len(b"binary-payload"),
                    "status": "active",
                    "source_type": "pwa_multipart_upload",
                },
            )

    def test_enforces_session_quota_by_count_and_size(self) -> None:
        store = InMemoryDocumentArtifactStore()
        store.save(
            DocumentArtifactRecord(
                artifact_id="artifact_existing",
                user_id="user_1",
                session_id="session_1",
                artifact_label="existing.png",
                source_type="pwa_multipart_upload",
                content_type="image/png",
                size_bytes=900,
                storage_key="documents/session_1/existing.png",
                local_path="C:/runtime/uploads/documents/session_1/existing.png",
            )
        )
        quota = EnforceSessionArtifactQuota(
            artifact_store=store,
            quota=SessionArtifactQuota(max_active_artifacts=1, max_total_bytes=1024),
        )

        with self.assertRaises(DocumentArtifactQuotaExceededError):
            quota.execute(user_id="user_1", session_id="session_1", incoming_size_bytes=200)

    def test_deletes_artifact_only_for_owning_session(self) -> None:
        with TemporaryDirectory() as temp_dir:
            uploads_root = Path(temp_dir) / "uploads"
            storage = FilesystemDocumentArtifactStorage(uploads_root)
            store = InMemoryDocumentArtifactStore()
            event_store = InMemoryEventStore()
            record = RegisterLocalDocumentArtifact(
                artifact_store=store,
                storage=storage,
                event_store=event_store,
            ).execute(
                user_id="user_1",
                session_id="session_1",
                artifact_label="contract.png",
                source_type="pwa_multipart_upload",
                content_type="image/png",
                payload=b"payload",
            )

            with self.assertRaises(DocumentArtifactOwnershipError):
                DeleteLocalDocumentArtifact(artifact_store=store, storage=storage).execute(
                    artifact_id=record.artifact_id,
                    user_id="user_2",
                    session_id="session_1",
                )

            deleted = DeleteLocalDocumentArtifact(
                artifact_store=store,
                storage=storage,
                event_store=event_store,
            ).execute(
                artifact_id=record.artifact_id,
                user_id="user_1",
                session_id="session_1",
            )

            self.assertEqual(deleted.status, DocumentArtifactStatus.DELETED)
            self.assertFalse(Path(deleted.local_path).exists())
            self.assertEqual(event_store.events[-1].event_type, EventType.DOCUMENT_DELETED)
            self.assertEqual(event_store.events[-1].metadata["artifact_id"], record.artifact_id)
            self.assertNotIn("local_path", event_store.events[-1].metadata)
            self.assertNotIn("artifact_label", event_store.events[-1].metadata)

    def test_expires_owned_active_artifact(self) -> None:
        with TemporaryDirectory() as temp_dir:
            uploads_root = Path(temp_dir) / "uploads"
            storage = FilesystemDocumentArtifactStorage(uploads_root)
            store = InMemoryDocumentArtifactStore()
            event_store = InMemoryEventStore()
            record = RegisterLocalDocumentArtifact(
                artifact_store=store,
                storage=storage,
            ).execute(
                artifact_id="artifact_expirable",
                user_id="user_1",
                session_id="session_1",
                artifact_label="contract.png",
                source_type="pwa_multipart_upload",
                content_type="image/png",
                payload=b"expirable-payload",
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )

            expired = ExpireDocumentArtifact(
                artifact_store=store,
                storage=storage,
                event_store=event_store,
            ).execute(
                artifact_id="artifact_expirable",
                user_id="user_1",
                session_id="session_1",
                expired_at=datetime.now(UTC),
                correlation_id="corr_retention_1",
                trace_id="trace_retention_1",
            )

            self.assertEqual(expired.status, DocumentArtifactStatus.EXPIRED)
            self.assertEqual(store.get("artifact_expirable").status, DocumentArtifactStatus.EXPIRED)
            self.assertFalse(Path(record.local_path).exists())
            self.assertEqual(
                event_store.events[-1].event_type,
                EventType.DOCUMENT_RETENTION_EXPIRED,
            )
            self.assertEqual(event_store.events[-1].metadata["artifact_id"], record.artifact_id)

    def test_expire_document_artifact_is_idempotent_after_first_transition(self) -> None:
        with TemporaryDirectory() as temp_dir:
            uploads_root = Path(temp_dir) / "uploads"
            storage = FilesystemDocumentArtifactStorage(uploads_root)
            store = InMemoryDocumentArtifactStore()
            event_store = InMemoryEventStore()
            record = RegisterLocalDocumentArtifact(
                artifact_store=store,
                storage=storage,
            ).execute(
                artifact_id="artifact_idempotent",
                user_id="user_1",
                session_id="session_1",
                artifact_label="contract.png",
                source_type="pwa_multipart_upload",
                content_type="image/png",
                payload=b"expirable-payload",
            )

            first_expired = ExpireDocumentArtifact(
                artifact_store=store,
                storage=storage,
                event_store=event_store,
            ).execute(
                artifact_id=record.artifact_id,
                user_id="user_1",
                session_id="session_1",
                correlation_id="corr_retention_1",
                trace_id="trace_retention_1",
            )
            second_expired = ExpireDocumentArtifact(
                artifact_store=store,
                storage=storage,
                event_store=event_store,
            ).execute(
                artifact_id=record.artifact_id,
                user_id="user_1",
                session_id="session_1",
                correlation_id="corr_retention_2",
                trace_id="trace_retention_2",
            )

            self.assertEqual(first_expired.status, DocumentArtifactStatus.EXPIRED)
            self.assertEqual(second_expired.status, DocumentArtifactStatus.EXPIRED)
            self.assertEqual(
                [event.event_type for event in event_store.events].count(
                    EventType.DOCUMENT_RETENTION_EXPIRED
                ),
                1,
            )
