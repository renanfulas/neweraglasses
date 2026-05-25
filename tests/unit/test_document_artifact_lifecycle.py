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
from new_era.infrastructure.documents.filesystem_document_artifact_storage import (
    FilesystemDocumentArtifactStorage,
)
from new_era.infrastructure.documents.in_memory_document_artifact_store import (
    InMemoryDocumentArtifactStore,
)


class DocumentArtifactLifecycleUseCasesTest(TestCase):
    def test_registers_local_document_artifact(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = InMemoryDocumentArtifactStore()
            storage = FilesystemDocumentArtifactStorage(Path(temp_dir) / "uploads")
            use_case = RegisterLocalDocumentArtifact(
                artifact_store=store,
                storage=storage,
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
            record = RegisterLocalDocumentArtifact(
                artifact_store=store,
                storage=storage,
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

            deleted = DeleteLocalDocumentArtifact(artifact_store=store, storage=storage).execute(
                artifact_id=record.artifact_id,
                user_id="user_1",
                session_id="session_1",
            )

            self.assertEqual(deleted.status, DocumentArtifactStatus.DELETED)
            self.assertFalse(Path(deleted.local_path).exists())

    def test_expires_owned_active_artifact(self) -> None:
        store = InMemoryDocumentArtifactStore()
        record = DocumentArtifactRecord(
            artifact_id="artifact_expirable",
            user_id="user_1",
            session_id="session_1",
            artifact_label="contract.png",
            source_type="pwa_multipart_upload",
            content_type="image/png",
            size_bytes=200,
            storage_key="documents/session_1/contract.png",
            local_path="C:/runtime/uploads/documents/session_1/contract.png",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        store.save(record)

        expired = ExpireDocumentArtifact(artifact_store=store).execute(
            artifact_id="artifact_expirable",
            user_id="user_1",
            session_id="session_1",
            expired_at=datetime.now(UTC),
        )

        self.assertEqual(expired.status, DocumentArtifactStatus.EXPIRED)
        self.assertEqual(store.get("artifact_expirable").status, DocumentArtifactStatus.EXPIRED)
