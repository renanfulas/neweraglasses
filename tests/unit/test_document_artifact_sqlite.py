from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from new_era.domain.documents import (
    ContractReviewAnalysis,
    DocumentAnalysisRecord,
    DocumentArtifactRecord,
    DocumentArtifactStatus,
)
from new_era.infrastructure.documents.sqlite_document_analysis_store import (
    SQLiteDocumentAnalysisStore,
)
from new_era.infrastructure.documents.sqlite_document_artifact_store import (
    SQLiteDocumentArtifactStore,
)


class DocumentArtifactSQLiteTest(TestCase):
    def test_sqlite_document_artifact_store_persists_records_across_instances(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "new_era.sqlite3"
            record = DocumentArtifactRecord(
                artifact_id="artifact_1",
                user_id="user_1",
                session_id="session_1",
                artifact_label="contract.png",
                source_type="pwa_multipart_upload",
                content_type="image/png",
                size_bytes=42,
                storage_key="session_1/artifact_1_contract.png",
                local_path=str(Path(temp_dir) / "uploads" / "session_1" / "artifact_1_contract.png"),
                metadata={"origin": "test"},
            )
            first_store = SQLiteDocumentArtifactStore(database_path)
            first_store.save(record)

            second_store = SQLiteDocumentArtifactStore(database_path)
            restored = second_store.get("artifact_1")
            listing = second_store.list_by_session(user_id="user_1", session_id="session_1")

            self.assertEqual(restored.artifact_label, "contract.png")
            self.assertEqual(restored.status, DocumentArtifactStatus.ACTIVE)
            self.assertEqual(restored.metadata["origin"], "test")
            self.assertEqual(listing[0].artifact_id, "artifact_1")

    def test_sqlite_document_artifact_store_filters_by_status(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "new_era.sqlite3"
            store = SQLiteDocumentArtifactStore(database_path)
            store.save(
                DocumentArtifactRecord(
                    artifact_id="artifact_active",
                    user_id="user_1",
                    session_id="session_1",
                    artifact_label="active.png",
                    source_type="pwa_multipart_upload",
                    content_type="image/png",
                    size_bytes=10,
                    storage_key="session_1/active.png",
                    local_path="C:/tmp/active.png",
                )
            )
            store.save(
                DocumentArtifactRecord(
                    artifact_id="artifact_deleted",
                    user_id="user_1",
                    session_id="session_1",
                    artifact_label="deleted.png",
                    source_type="pwa_multipart_upload",
                    content_type="image/png",
                    size_bytes=10,
                    storage_key="session_1/deleted.png",
                    local_path="C:/tmp/deleted.png",
                    status=DocumentArtifactStatus.DELETED,
                    deleted_at=datetime.now(UTC),
                )
            )

            active_records = store.list_by_session(
                user_id="user_1",
                session_id="session_1",
                status=DocumentArtifactStatus.ACTIVE,
            )

            self.assertEqual([record.artifact_id for record in active_records], ["artifact_active"])

    def test_document_analysis_store_persists_optional_artifact_id(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "new_era.sqlite3"
            analysis_store = SQLiteDocumentAnalysisStore(database_path)
            analysis_store.save(
                DocumentAnalysisRecord(
                    analysis_id="analysis_1",
                    artifact_id="artifact_1",
                    user_id="user_1",
                    session_id="session_1",
                    observation_id="obs_1",
                    trace_id="trace_1",
                    source_type="pwa_upload",
                    analysis=ContractReviewAnalysis(
                        extracted_text="Contrato de teste.",
                        source_confidence=0.9,
                        review_confidence=0.88,
                        summary_title="Review",
                        summary_body="Needs review",
                    ),
                )
            )

            restored = SQLiteDocumentAnalysisStore(database_path).get("analysis_1")

            self.assertEqual(restored.artifact_id, "artifact_1")
