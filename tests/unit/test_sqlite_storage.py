from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from new_era.application.ports import DocumentAnalysisJobPayload
from new_era.application.services import SimulationRuntime
from new_era.domain.attention import AttentionMode
from new_era.domain.documents import (
    ContractFinding,
    ContractFindingType,
    ContractReviewAnalysis,
    DocumentAnalysisRecord,
)
from new_era.domain.events import Event, EventType
from new_era.domain.jobs import JobRecord, JobStatus, JobType
from new_era.domain.sessions import UserSession
from new_era.infrastructure.documents import SQLiteDocumentAnalysisStore
from new_era.infrastructure.events import SQLiteEventStore
from new_era.infrastructure.jobs import (
    SQLiteDocumentAnalysisJobPayloadStore,
    SQLiteJobStore,
)
from new_era.infrastructure.sessions import SQLiteSessionStore


class SQLiteStorageTest(TestCase):
    def test_event_store_persists_events_across_instances(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "new_era.sqlite3"
            first_store = SQLiteEventStore(database_path)
            first_store.append(
                Event(
                    event_type=EventType.OBSERVATION_CREATED,
                    user_id="user_1",
                    session_id="session_1",
                    module="grocery",
                    correlation_id="corr_1",
                    trace_id="trace_1",
                    metadata={"summary": "Missing eggs"},
                )
            )

            second_store = SQLiteEventStore(database_path)
            events = second_store.list_events(
                user_id="user_1",
                session_id="session_1",
                module="grocery",
            )

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].metadata["summary"], "Missing eggs")

    def test_session_store_persists_user_sessions_across_instances(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "new_era.sqlite3"
            first_store = SQLiteSessionStore(database_path)
            first_store.save(
                UserSession(
                    user_id="user_1",
                    session_id="session_1",
                    module="documents",
                    title="Contract review",
                )
            )

            second_store = SQLiteSessionStore(database_path)
            sessions = second_store.list_by_user(user_id="user_1", module="documents")

            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].session_id, "session_1")

    def test_job_store_persists_and_can_find_by_idempotency_key(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "new_era.sqlite3"
            first_store = SQLiteJobStore(database_path)
            first_store.save(
                JobRecord(
                    job_id="job_1",
                    job_type=JobType.DOCUMENT_CONTRACT_ANALYSIS,
                    status=JobStatus.QUEUED,
                    user_id="user_1",
                    session_id="session_1",
                    module="documents",
                    idempotency_key="idem_12345678",
                    metadata={"artifact_label": "contract.pdf"},
                )
            )

            second_store = SQLiteJobStore(database_path)
            job = second_store.get("job_1")
            found = second_store.find_by_idempotency_key(
                job_type=JobType.DOCUMENT_CONTRACT_ANALYSIS,
                user_id="user_1",
                session_id="session_1",
                idempotency_key="idem_12345678",
            )

            self.assertIsNotNone(job)
            self.assertEqual(job.status, JobStatus.QUEUED)
            self.assertEqual(found.job_id, "job_1")

    def test_job_store_persists_updates_across_instances(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "new_era.sqlite3"
            first_store = SQLiteJobStore(database_path)
            first_store.save(
                JobRecord(
                    job_id="job_1",
                    job_type=JobType.DOCUMENT_CONTRACT_ANALYSIS,
                    status=JobStatus.QUEUED,
                    user_id="user_1",
                    session_id="session_1",
                    module="documents",
                    idempotency_key="idem_12345678",
                )
            )
            first_store.update(
                replace(
                    first_store.get("job_1"),
                    status=JobStatus.SUCCEEDED,
                    attempts=1,
                    result_id="analysis_1",
                    updated_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                )
            )

            second_store = SQLiteJobStore(database_path)
            job = second_store.get("job_1")

            self.assertEqual(job.status, JobStatus.SUCCEEDED)
            self.assertEqual(job.result_id, "analysis_1")
            self.assertEqual(job.attempts, 1)

    def test_document_analysis_store_persists_records_across_instances(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "new_era.sqlite3"
            analysis = ContractReviewAnalysis(
                extracted_text="Contrato com multa e fidelidade.",
                source_confidence=0.91,
                review_confidence=0.88,
                summary_title="Contract clause needs attention",
                summary_body="Possible cancellation fee and minimum commitment.",
                findings=(
                    ContractFinding(
                        finding_type=ContractFindingType.CANCELLATION_FEE,
                        label="cancellation fee",
                        excerpt="multa",
                        confidence=0.92,
                    ),
                ),
            )
            record = DocumentAnalysisRecord(
                analysis_id="analysis_1",
                user_id="user_1",
                session_id="session_1",
                observation_id="obs_1",
                trace_id="trace_1",
                source_type="pwa_upload",
                analysis=analysis,
            )
            first_store = SQLiteDocumentAnalysisStore(database_path)
            first_store.save(record)

            second_store = SQLiteDocumentAnalysisStore(database_path)
            restored = second_store.get("analysis_1")
            listing = second_store.list_by_session(session_id="session_1")

            self.assertEqual(restored.analysis.summary_title, analysis.summary_title)
            self.assertEqual(restored.analysis.findings[0].finding_type, ContractFindingType.CANCELLATION_FEE)
            self.assertEqual(listing[0].analysis_id, "analysis_1")

    def test_document_analysis_job_payload_store_persists_and_deletes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "new_era.sqlite3"
            payload = DocumentAnalysisJobPayload(
                job_id="job_1",
                user_id="user_1",
                session_id="session_1",
                artifact_label="contract.pdf",
                source_type="pwa_upload",
                document_text="Contrato com multa.",
                document_image_base64=None,
                confidence=0.92,
                mode=AttentionMode.BALANCED,
                recent_category_count=0,
                observation_id="obs_1",
                correlation_id="corr_1",
                trace_id="trace_1",
            )
            first_store = SQLiteDocumentAnalysisJobPayloadStore(database_path)
            first_store.save(payload)

            second_store = SQLiteDocumentAnalysisJobPayloadStore(database_path)
            restored = second_store.get("job_1")
            self.assertEqual(restored.artifact_label, "contract.pdf")
            self.assertEqual(restored.mode, AttentionMode.BALANCED)

            second_store.delete("job_1")
            third_store = SQLiteDocumentAnalysisJobPayloadStore(database_path)
            self.assertIsNone(third_store.get("job_1"))

    def test_runtime_uses_sqlite_backed_stores_when_storage_path_is_provided(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "new_era.sqlite3"
            runtime = SimulationRuntime.build_default(storage_path=database_path)

            self.assertIsInstance(runtime.event_store, SQLiteEventStore)
            self.assertIsInstance(runtime.session_store, SQLiteSessionStore)
            self.assertIsInstance(runtime.job_store, SQLiteJobStore)
            self.assertIsInstance(runtime.document_analysis_store, SQLiteDocumentAnalysisStore)
            self.assertIsInstance(
                runtime.document_job_payload_store,
                SQLiteDocumentAnalysisJobPayloadStore,
            )
