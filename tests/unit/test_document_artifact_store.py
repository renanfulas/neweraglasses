from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from new_era.domain.documents import DocumentArtifactRecord, DocumentArtifactStatus
from new_era.infrastructure.documents.in_memory_document_artifact_store import (
    InMemoryDocumentArtifactStore,
)
from new_era.infrastructure.documents.sqlite_document_artifact_store import (
    SQLiteDocumentArtifactStore,
)


class InMemoryDocumentArtifactStoreTest(TestCase):
    def test_lists_records_by_session_and_status(self) -> None:
        store = InMemoryDocumentArtifactStore()
        active_record = DocumentArtifactRecord(
            artifact_id="artifact_active",
            user_id="user_1",
            session_id="session_1",
            artifact_label="contract-a.png",
            source_type="pwa_multipart_upload",
            content_type="image/png",
            size_bytes=120,
            storage_key="documents/session_1/contract-a.png",
            local_path="C:/runtime/uploads/documents/session_1/contract-a.png",
        )
        deleted_record = DocumentArtifactRecord(
            artifact_id="artifact_deleted",
            user_id="user_1",
            session_id="session_1",
            artifact_label="contract-b.png",
            source_type="pwa_multipart_upload",
            content_type="image/png",
            size_bytes=300,
            storage_key="documents/session_1/contract-b.png",
            local_path="C:/runtime/uploads/documents/session_1/contract-b.png",
            status=DocumentArtifactStatus.DELETED,
            deleted_at=datetime.now(UTC),
        )

        store.save(active_record)
        store.save(deleted_record)

        active_records = store.list_by_session(
            user_id="user_1",
            session_id="session_1",
            status=DocumentArtifactStatus.ACTIVE,
        )

        self.assertEqual([record.artifact_id for record in active_records], ["artifact_active"])


class SQLiteDocumentArtifactStoreTest(TestCase):
    def test_persists_document_artifact_lifecycle_fields(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "new_era.sqlite3"
            now = datetime.now(UTC)
            store = SQLiteDocumentArtifactStore(database_path)
            record = DocumentArtifactRecord(
                artifact_id="artifact_1",
                user_id="user_1",
                session_id="session_1",
                artifact_label="contract.png",
                source_type="pwa_multipart_upload",
                content_type="image/png",
                size_bytes=512,
                storage_key="documents/session_1/contract.png",
                local_path=str(Path(temp_dir) / "uploads" / "contract.png"),
                expires_at=now + timedelta(hours=1),
                metadata={"origin": "camera"},
            )
            store.save(record)

            restored = SQLiteDocumentArtifactStore(database_path).get("artifact_1")
            listing = SQLiteDocumentArtifactStore(database_path).list_by_session(
                user_id="user_1",
                session_id="session_1",
            )

            self.assertEqual(restored.storage_key, "documents/session_1/contract.png")
            self.assertEqual(restored.metadata["origin"], "camera")
            self.assertEqual(restored.status, DocumentArtifactStatus.ACTIVE)
            self.assertEqual([item.artifact_id for item in listing], ["artifact_1"])

    def test_rejects_unsafe_storage_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "safe relative path"):
            DocumentArtifactRecord(
                artifact_id="artifact_unsafe",
                user_id="user_1",
                session_id="session_1",
                artifact_label="contract.png",
                source_type="pwa_multipart_upload",
                content_type="image/png",
                size_bytes=10,
                storage_key="../escape.png",
                local_path="C:/runtime/uploads/documents/session_1/escape.png",
            )
