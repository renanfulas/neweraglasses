from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import sleep
from unittest import TestCase

from new_era.application.ports import DocumentAnalysisJobPayloadStore
from new_era.application.use_cases import (
    AdvanceDocumentAnalysisJob,
    EnqueueDocumentAnalysisJob,
    GetJobStatus,
    ListJobsBySession,
    PolicyRejectedError,
    RunDocumentAnalysisJob,
)
from new_era.application.use_cases.document_artifact_lifecycle import (
    ExpireDocumentArtifact,
    RegisterLocalDocumentArtifact,
)
from new_era.application.use_cases.document_analysis_jobs import SessionActiveJobQuota
from new_era.domain.attention import AttentionMode
from new_era.domain.documents import (
    ContractReviewAnalysis,
    DocumentAnalysisRecord,
    DocumentArtifactStatus,
)
from new_era.domain.events import EventType
from new_era.domain.jobs import JobExecutionPolicy, JobRecord, JobStatus, JobType
from new_era.infrastructure.documents import InMemoryDocumentAnalysisStore
from new_era.infrastructure.documents.filesystem_document_artifact_storage import (
    FilesystemDocumentArtifactStorage,
)
from new_era.infrastructure.documents.in_memory_document_artifact_store import (
    InMemoryDocumentArtifactStore,
)
from new_era.infrastructure.events import InMemoryEventStore
from new_era.infrastructure.jobs import (
    InMemoryDocumentAnalysisJobPayloadStore,
    InMemoryJobStore,
)


@dataclass(frozen=True, slots=True)
class FakeDocumentReviewResult:
    analysis_record: DocumentAnalysisRecord


class FakeDocumentProcessor:
    def __init__(
        self,
        *,
        analysis_store: InMemoryDocumentAnalysisStore,
        failures_before_success: int = 0,
        sleep_seconds: float = 0.0,
    ) -> None:
        self.analysis_store = analysis_store
        self.failures_before_success = failures_before_success
        self.sleep_seconds = sleep_seconds
        self.calls = 0

    def process_contract_review(
        self,
        *,
        observation_id: str,
        user_id: str,
        session_id: str,
        document_text: str | None,
        document_image_base64: str | None,
        confidence: float | None,
        mode: AttentionMode,
        recent_category_count: int,
        correlation_id: str,
        trace_id: str,
        artifact_id: str | None = None,
    ) -> FakeDocumentReviewResult:
        self.calls += 1
        if self.sleep_seconds:
            sleep(self.sleep_seconds)
        if self.calls <= self.failures_before_success:
            raise RuntimeError("temporary provider failure")
        record = DocumentAnalysisRecord(
            user_id=user_id,
            session_id=session_id,
            observation_id=observation_id,
            trace_id=trace_id,
            source_type="plain_text" if document_text else "image_ocr",
            artifact_id=artifact_id,
            analysis=ContractReviewAnalysis(
                extracted_text=document_text or "OCR text",
                source_confidence=confidence or 0.92,
                review_confidence=0.88,
                summary_title="Contract clause needs attention",
                summary_body="This clause deserves review before signing.",
            ),
        )
        self.analysis_store.save(record)
        return FakeDocumentReviewResult(analysis_record=record)


class BlockingSaveJobStore(InMemoryJobStore):
    def __init__(self) -> None:
        super().__init__()
        self.save_started = Event()
        self.release_save = Event()
        self._blocked_once = False

    def save(self, job: JobRecord) -> None:
        if not self._blocked_once:
            self._blocked_once = True
            self.save_started.set()
            self.release_save.wait(timeout=2)
        super().save(job)


class DocumentAnalysisJobsTest(TestCase):
    def _build_analysis_store(self) -> InMemoryDocumentAnalysisStore:
        return InMemoryDocumentAnalysisStore()

    def _build_payload_store(self) -> DocumentAnalysisJobPayloadStore:
        return InMemoryDocumentAnalysisJobPayloadStore()

    def _save_analysis(
        self,
        store: InMemoryDocumentAnalysisStore,
        *,
        user_id: str = "user_1",
        session_id: str = "session_1",
        observation_id: str = "obs_1",
        trace_id: str = "trace_1",
    ) -> DocumentAnalysisRecord:
        record = DocumentAnalysisRecord(
            user_id=user_id,
            session_id=session_id,
            observation_id=observation_id,
            trace_id=trace_id,
            source_type="pwa_upload",
            analysis=ContractReviewAnalysis(
                extracted_text="Automatic renewal clause.",
                source_confidence=0.91,
                review_confidence=0.88,
                summary_title="Contract clause needs attention",
                summary_body="This clause deserves review before signing.",
            ),
        )
        store.save(record)
        return record

    def test_enqueues_document_analysis_job_and_records_event(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        payload_store = self._build_payload_store()
        use_case = EnqueueDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            payload_store=payload_store,
        )

        job = use_case.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_12345678",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
            document_text="Contrato com renovacao automatica e multa de cancelamento.",
        )

        self.assertEqual(job.status.value, "queued")
        self.assertEqual(job_store.get(job.job_id), job)
        self.assertIsNotNone(payload_store.get(job.job_id))
        self.assertEqual(event_store.events[-1].event_type, EventType.JOB_STARTED)

    def test_reuses_job_for_same_idempotency_key(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        use_case = EnqueueDocumentAnalysisJob(job_store=job_store, event_store=event_store)

        first_job = use_case.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_12345678",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
        )
        second_job = use_case.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_12345678",
            correlation_id="corr_2",
            trace_id="trace_2",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
        )

        self.assertEqual(first_job.job_id, second_job.job_id)
        self.assertEqual(len(event_store.events), 1)

    def test_reuses_job_for_same_idempotency_key_and_same_payload_fingerprint(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        payload_store = self._build_payload_store()
        use_case = EnqueueDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            payload_store=payload_store,
        )

        first_job = use_case.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_same_payload",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
            document_text="Clausula de renovacao automatica.",
        )
        second_job = use_case.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_same_payload",
            correlation_id="corr_2",
            trace_id="trace_2",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
            document_text="Clausula de renovacao automatica.",
        )

        self.assertEqual(first_job.job_id, second_job.job_id)
        self.assertEqual(first_job.metadata["payload_fingerprint"], second_job.metadata["payload_fingerprint"])
        self.assertEqual(len(event_store.events), 1)
        self.assertIsNotNone(payload_store.get(first_job.job_id))

    def test_rejects_same_idempotency_key_with_different_payload_fingerprint(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        use_case = EnqueueDocumentAnalysisJob(job_store=job_store, event_store=event_store)

        use_case.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_payload_conflict",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
            document_text="Clausula de renovacao automatica.",
        )

        with self.assertRaises(PolicyRejectedError) as raised:
            use_case.execute(
                user_id="user_1",
                session_id="session_1",
                idempotency_key="idem_payload_conflict",
                correlation_id="corr_2",
                trace_id="trace_2",
                artifact_label="gym-contract.pdf",
                source_type="pwa_upload",
                document_text="Clausula de multa por cancelamento.",
            )

        self.assertEqual(raised.exception.rejection.code, "idempotency_payload_mismatch")
        self.assertEqual(raised.exception.rejection.reason, "idempotency_mismatch")
        self.assertEqual(len(event_store.events), 1)

    def test_rejects_when_session_active_job_quota_is_full(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        use_case = EnqueueDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            active_job_quota=SessionActiveJobQuota(max_active_jobs=2),
        )
        job_store.save(
            JobRecord(
                job_id="job_queued",
                job_type=JobType.DOCUMENT_CONTRACT_ANALYSIS,
                status=JobStatus.QUEUED,
                user_id="user_1",
                session_id="session_1",
                module="documents",
                idempotency_key="idem_existing_queued",
            )
        )
        job_store.save(
            JobRecord(
                job_id="job_running",
                job_type=JobType.DOCUMENT_CONTRACT_ANALYSIS,
                status=JobStatus.RUNNING,
                user_id="user_1",
                session_id="session_1",
                module="documents",
                idempotency_key="idem_existing_running",
            )
        )
        job_store.save(
            JobRecord(
                job_id="job_succeeded",
                job_type=JobType.DOCUMENT_CONTRACT_ANALYSIS,
                status=JobStatus.SUCCEEDED,
                user_id="user_1",
                session_id="session_1",
                module="documents",
                idempotency_key="idem_existing_succeeded",
            )
        )

        with self.assertRaises(PolicyRejectedError) as raised:
            use_case.execute(
                user_id="user_1",
                session_id="session_1",
                idempotency_key="idem_new_job",
                correlation_id="corr_1",
                trace_id="trace_1",
                artifact_label="gym-contract.pdf",
                source_type="pwa_upload",
                document_text="Contrato com fidelidade de 12 meses.",
            )

        self.assertEqual(raised.exception.rejection.code, "session_active_job_limit_exceeded")
        self.assertEqual(raised.exception.rejection.current, 2)
        self.assertEqual(raised.exception.rejection.limit, 2)
        self.assertEqual(event_store.events[-1].event_type, EventType.RATE_LIMIT_EXCEEDED)

    def test_enforces_active_job_quota_atomically_per_session(self) -> None:
        job_store = BlockingSaveJobStore()
        event_store = InMemoryEventStore()
        use_case = EnqueueDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            active_job_quota=SessionActiveJobQuota(max_active_jobs=1),
        )

        def enqueue(suffix: str):
            return use_case.execute(
                user_id="user_atomic",
                session_id="session_atomic",
                idempotency_key=f"idem_atomic_{suffix}",
                correlation_id=f"corr_atomic_{suffix}",
                trace_id=f"trace_atomic_{suffix}",
                artifact_label=f"contract-{suffix}.pdf",
                source_type="pwa_upload",
                document_text="Contrato com fidelidade de 12 meses.",
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(enqueue, "one")
            self.assertTrue(job_store.save_started.wait(timeout=1))
            second_future = executor.submit(enqueue, "two")
            sleep(0.05)
            job_store.release_save.set()
            first_job = first_future.result(timeout=1)
            with self.assertRaises(PolicyRejectedError) as raised:
                second_future.result(timeout=1)

        self.assertEqual(first_job.session_id, "session_atomic")
        self.assertEqual(raised.exception.rejection.code, "session_active_job_limit_exceeded")
        self.assertEqual(
            job_store.count_by_session_statuses(
                user_id="user_atomic",
                session_id="session_atomic",
                module="documents",
                statuses=(JobStatus.QUEUED, JobStatus.RUNNING),
            ),
            1,
        )

    def test_runner_processes_document_job_and_persists_result(self) -> None:
        with TemporaryDirectory() as temp_dir:
            job_store = InMemoryJobStore()
            event_store = InMemoryEventStore()
            payload_store = InMemoryDocumentAnalysisJobPayloadStore()
            analysis_store = self._build_analysis_store()
            artifact_store = InMemoryDocumentArtifactStore()
            storage = FilesystemDocumentArtifactStorage(Path(temp_dir) / "uploads")
            artifact_record = RegisterLocalDocumentArtifact(
                artifact_store=artifact_store,
                storage=storage,
            ).execute(
                user_id="user_1",
                session_id="session_1",
                artifact_label="gym-contract.pdf",
                source_type="pwa_upload",
                content_type="application/pdf",
                payload=b"pdf-bytes",
            )
            enqueue = EnqueueDocumentAnalysisJob(
                job_store=job_store,
                event_store=event_store,
                payload_store=payload_store,
            )
            processor = FakeDocumentProcessor(analysis_store=analysis_store)
            runner = RunDocumentAnalysisJob(
                job_store=job_store,
                event_store=event_store,
                payload_store=payload_store,
                document_processor=processor,
                artifact_expirer=ExpireDocumentArtifact(
                    artifact_store=artifact_store,
                    storage=storage,
                    event_store=event_store,
                ),
            )
            job = enqueue.execute(
                user_id="user_1",
                session_id="session_1",
                idempotency_key="idem_real_worker",
                correlation_id="corr_1",
                trace_id="trace_1",
                artifact_label="gym-contract.pdf",
                source_type="pwa_upload",
                artifact_id=artifact_record.artifact_id,
                document_text="Contrato com renovacao automatica e multa de cancelamento.",
            )

            completed_job = runner.execute(job_id=job.job_id)

            self.assertEqual(completed_job.status, JobStatus.SUCCEEDED)
            self.assertEqual(completed_job.attempts, 1)
            self.assertIsNotNone(completed_job.result_id)
            self.assertEqual(completed_job.metadata["analysis_id"], completed_job.result_id)
            self.assertIsNotNone(analysis_store.get(completed_job.result_id))
            self.assertIsNone(payload_store.get(job.job_id))
            self.assertEqual(
                [event.event_type for event in event_store.events],
                [
                    EventType.JOB_STARTED,
                    EventType.JOB_STATUS_UPDATED,
                    EventType.JOB_COMPLETED,
                    EventType.DOCUMENT_RETENTION_EXPIRED,
                ],
            )
            self.assertEqual(
                artifact_store.get(artifact_record.artifact_id).status,
                DocumentArtifactStatus.EXPIRED,
            )
            self.assertFalse(Path(artifact_record.local_path).exists())

    def test_runner_retries_transient_failures_before_succeeding(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        payload_store = InMemoryDocumentAnalysisJobPayloadStore()
        analysis_store = self._build_analysis_store()
        enqueue = EnqueueDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            payload_store=payload_store,
            execution_policy=JobExecutionPolicy(max_attempts=2, timeout_seconds=1.0),
        )
        processor = FakeDocumentProcessor(
            analysis_store=analysis_store,
            failures_before_success=1,
        )
        runner = RunDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            payload_store=payload_store,
            document_processor=processor,
        )
        job = enqueue.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_retry_worker",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
            document_text="Contrato com renovacao automatica e multa de cancelamento.",
        )

        completed_job = runner.execute(job_id=job.job_id)

        self.assertEqual(completed_job.status, JobStatus.SUCCEEDED)
        self.assertEqual(completed_job.attempts, 2)
        self.assertEqual(processor.calls, 2)
        self.assertIn(EventType.AI_CALL_FAILED, [event.event_type for event in event_store.events])
        self.assertEqual(event_store.events[-1].event_type, EventType.JOB_COMPLETED)

    def test_runner_fails_after_exhausting_attempts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            job_store = InMemoryJobStore()
            event_store = InMemoryEventStore()
            payload_store = InMemoryDocumentAnalysisJobPayloadStore()
            analysis_store = self._build_analysis_store()
            artifact_store = InMemoryDocumentArtifactStore()
            storage = FilesystemDocumentArtifactStorage(Path(temp_dir) / "uploads")
            artifact_record = RegisterLocalDocumentArtifact(
                artifact_store=artifact_store,
                storage=storage,
            ).execute(
                user_id="user_1",
                session_id="session_1",
                artifact_label="gym-contract.pdf",
                source_type="pwa_upload",
                content_type="application/pdf",
                payload=b"pdf-bytes",
            )
            enqueue = EnqueueDocumentAnalysisJob(
                job_store=job_store,
                event_store=event_store,
                payload_store=payload_store,
                execution_policy=JobExecutionPolicy(max_attempts=2, timeout_seconds=1.0),
            )
            processor = FakeDocumentProcessor(
                analysis_store=analysis_store,
                failures_before_success=10,
            )
            runner = RunDocumentAnalysisJob(
                job_store=job_store,
                event_store=event_store,
                payload_store=payload_store,
                document_processor=processor,
                artifact_expirer=ExpireDocumentArtifact(
                    artifact_store=artifact_store,
                    storage=storage,
                    event_store=event_store,
                ),
            )
            job = enqueue.execute(
                user_id="user_1",
                session_id="session_1",
                idempotency_key="idem_fail_worker",
                correlation_id="corr_1",
                trace_id="trace_1",
                artifact_label="gym-contract.pdf",
                source_type="pwa_upload",
                artifact_id=artifact_record.artifact_id,
                document_text="Contrato com renovacao automatica e multa de cancelamento.",
            )

            failed_job = runner.execute(job_id=job.job_id)

            self.assertEqual(failed_job.status, JobStatus.FAILED)
            self.assertEqual(failed_job.attempts, 2)
            self.assertEqual(failed_job.error_code, "execution_error")
            self.assertIsNone(payload_store.get(job.job_id))
            self.assertEqual(event_store.events[-2].event_type, EventType.JOB_FAILED)
            self.assertEqual(
                event_store.events[-1].event_type,
                EventType.DOCUMENT_RETENTION_EXPIRED,
            )
            self.assertEqual(
                artifact_store.get(artifact_record.artifact_id).status,
                DocumentArtifactStatus.EXPIRED,
            )
            self.assertFalse(Path(artifact_record.local_path).exists())

    def test_runner_applies_timeout_policy(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        payload_store = InMemoryDocumentAnalysisJobPayloadStore()
        analysis_store = self._build_analysis_store()
        enqueue = EnqueueDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            payload_store=payload_store,
            execution_policy=JobExecutionPolicy(max_attempts=1, timeout_seconds=0.01),
        )
        processor = FakeDocumentProcessor(
            analysis_store=analysis_store,
            sleep_seconds=0.05,
        )
        runner = RunDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            payload_store=payload_store,
            document_processor=processor,
        )
        job = enqueue.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_timeout_worker",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
            document_text="Contrato com renovacao automatica e multa de cancelamento.",
        )

        failed_job = runner.execute(job_id=job.job_id)

        self.assertEqual(failed_job.status, JobStatus.FAILED)
        self.assertEqual(failed_job.error_code, "timeout")
        self.assertEqual(failed_job.attempts, 1)

    def test_reads_job_status(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        enqueue = EnqueueDocumentAnalysisJob(job_store=job_store, event_store=event_store)
        job = enqueue.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_12345678",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
        )

        status = GetJobStatus(job_store=job_store).execute(job_id=job.job_id)

        self.assertEqual(status, job)

    def test_lists_jobs_for_session_newest_first(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        enqueue = EnqueueDocumentAnalysisJob(job_store=job_store, event_store=event_store)
        older_job = enqueue.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_older_12345678",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="older-contract.pdf",
            source_type="pwa_upload",
            document_text="Contrato com renovacao automatica e multa de cancelamento.",
        )
        sleep(0.001)
        newer_job = enqueue.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_newer_12345678",
            correlation_id="corr_2",
            trace_id="trace_2",
            artifact_label="newer-contract.pdf",
            source_type="pwa_upload",
            document_text="Contrato com fidelidade de 12 meses e multa de cancelamento.",
        )
        enqueue.execute(
            user_id="other_user",
            session_id="session_1",
            idempotency_key="idem_other_12345678",
            correlation_id="corr_3",
            trace_id="trace_3",
            artifact_label="other-contract.pdf",
            source_type="pwa_upload",
            document_text="Contrato com renovacao automatica e multa de cancelamento.",
        )

        jobs = ListJobsBySession(job_store=job_store).execute(
            user_id="user_1",
            session_id="session_1",
            module="documents",
        )

        self.assertEqual([job.job_id for job in jobs], [newer_job.job_id, older_job.job_id])

    def test_advances_job_through_running_and_succeeded(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        analysis_store = self._build_analysis_store()
        record = self._save_analysis(analysis_store)
        enqueue = EnqueueDocumentAnalysisJob(job_store=job_store, event_store=event_store)
        advance = AdvanceDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            document_analysis_store=analysis_store,
        )
        job = enqueue.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_12345678",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
        )

        running_job = advance.execute(
            job_id=job.job_id,
            target_status=JobStatus.RUNNING,
            correlation_id="corr_2",
            trace_id="trace_1",
        )
        succeeded_job = advance.execute(
            job_id=job.job_id,
            target_status=JobStatus.SUCCEEDED,
            correlation_id="corr_3",
            trace_id="trace_1",
            analysis_id=record.analysis_id,
        )

        self.assertEqual(running_job.status, JobStatus.RUNNING)
        self.assertEqual(succeeded_job.status, JobStatus.SUCCEEDED)
        self.assertEqual(succeeded_job.metadata["analysis_id"], record.analysis_id)
        self.assertEqual(
            [event.event_type for event in event_store.events],
            [
                EventType.JOB_STARTED,
                EventType.JOB_STATUS_UPDATED,
                EventType.JOB_COMPLETED,
            ],
        )
        self.assertEqual(event_store.events[-1].metadata["analysis_id"], record.analysis_id)

    def test_requires_analysis_id_when_succeeding_document_job(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        analysis_store = self._build_analysis_store()
        enqueue = EnqueueDocumentAnalysisJob(job_store=job_store, event_store=event_store)
        advance = AdvanceDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            document_analysis_store=analysis_store,
        )
        job = enqueue.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_12345678",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
        )
        advance.execute(
            job_id=job.job_id,
            target_status=JobStatus.RUNNING,
            correlation_id="corr_2",
            trace_id="trace_1",
        )

        with self.assertRaisesRegex(
            ValueError,
            "analysis_id is required when completing document analysis jobs",
        ):
            advance.execute(
                job_id=job.job_id,
                target_status=JobStatus.SUCCEEDED,
                correlation_id="corr_3",
                trace_id="trace_1",
            )

    def test_rejects_invalid_job_transition(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        enqueue = EnqueueDocumentAnalysisJob(job_store=job_store, event_store=event_store)
        advance = AdvanceDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            document_analysis_store=self._build_analysis_store(),
        )
        job = enqueue.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_12345678",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
        )

        with self.assertRaises(ValueError):
            advance.execute(
                job_id=job.job_id,
                target_status=JobStatus.SUCCEEDED,
                correlation_id="corr_2",
                trace_id="trace_1",
            )
