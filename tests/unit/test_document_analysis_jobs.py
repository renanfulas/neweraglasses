from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from unittest import TestCase

from new_era.application.ports import DocumentAnalysisJobPayloadStore
from new_era.application.use_cases import (
    AdvanceDocumentAnalysisJob,
    EnqueueDocumentAnalysisJob,
    GetJobStatus,
    RunDocumentAnalysisJob,
)
from new_era.domain.attention import AttentionMode
from new_era.domain.documents import ContractReviewAnalysis, DocumentAnalysisRecord
from new_era.domain.events import EventType
from new_era.domain.jobs import JobExecutionPolicy, JobStatus
from new_era.infrastructure.documents import InMemoryDocumentAnalysisStore
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
            analysis=ContractReviewAnalysis(
                extracted_text=document_text or "OCR text",
                source_confidence=confidence or 0.92,
                review_confidence=0.88,
                summary_title="Contract clause needs attention",
                summary_body="This clause deserves review before signing.",
            ).to_dict(),
        )
        self.analysis_store.save(record)
        return FakeDocumentReviewResult(analysis_record=record)


class DocumentAnalysisJobsTest(TestCase):
    def _build_analysis_store(self) -> InMemoryDocumentAnalysisStore:
        return InMemoryDocumentAnalysisStore()

    def _build_payload_store(self) -> DocumentAnalysisJobPayloadStore:
        return InMemoryDocumentAnalysisJobPayloadStore()

    def _save_analysis(
        self,
        store: InMemoryDocumentAnalysisStore,
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
            source_type="plain_text",
            analysis=ContractReviewAnalysis(
                extracted_text="contract text",
                source_confidence=0.92,
                review_confidence=0.88,
                summary_title="Contract clause needs attention",
                summary_body="This clause deserves review before signing.",
            ).to_dict(),
        )
        store.save(record)
        return record

    def test_enqueues_job_and_persists_payload(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        payload_store = self._build_payload_store()
        enqueue = EnqueueDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            payload_store=payload_store,
            execution_policy=JobExecutionPolicy(max_attempts=3, timeout_seconds=10.0),
        )

        job = enqueue.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_12345678",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
            document_text="contract body",
            mode=AttentionMode.BALANCED,
        )

        self.assertEqual(job.status, JobStatus.QUEUED)
        self.assertIsNotNone(payload_store.get(job.job_id))
        self.assertEqual(event_store.events[-1].event_type, EventType.JOB_STARTED)

    def test_reuses_existing_job_for_same_idempotency_key(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        payload_store = self._build_payload_store()
        enqueue = EnqueueDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            payload_store=payload_store,
        )

        first = enqueue.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_12345678",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
            document_text="contract body",
        )
        second = enqueue.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_12345678",
            correlation_id="corr_2",
            trace_id="trace_2",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
            document_text="contract body updated",
        )

        self.assertEqual(first.job_id, second.job_id)
        self.assertEqual(len(event_store.events), 1)

    def test_runs_job_successfully_and_persists_result(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        payload_store = self._build_payload_store()
        analysis_store = self._build_analysis_store()
        enqueue = EnqueueDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            payload_store=payload_store,
            execution_policy=JobExecutionPolicy(max_attempts=1, timeout_seconds=1.0),
        )
        processor = FakeDocumentProcessor(analysis_store=analysis_store)
        runner = RunDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            payload_store=payload_store,
            document_processor=processor,
        )

        job = enqueue.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_success_123",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
            document_text="contract body",
        )
        completed = runner.execute(job.job_id)

        self.assertEqual(completed.status, JobStatus.SUCCEEDED)
        self.assertIsNotNone(completed.result_id)
        self.assertIsNone(payload_store.get(job.job_id))
        self.assertEqual(processor.calls, 1)
        self.assertEqual(event_store.events[-1].event_type, EventType.JOB_COMPLETED)

    def test_retries_before_succeeding(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        payload_store = self._build_payload_store()
        analysis_store = self._build_analysis_store()
        enqueue = EnqueueDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            payload_store=payload_store,
            execution_policy=JobExecutionPolicy(
                max_attempts=3,
                timeout_seconds=1.0,
                retry_backoff_seconds=0.0,
            ),
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
            idempotency_key="idem_retry_123",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
            document_text="contract body",
        )
        completed = runner.execute(job.job_id)

        self.assertEqual(completed.status, JobStatus.SUCCEEDED)
        self.assertEqual(processor.calls, 2)
        self.assertEqual(completed.attempts, 2)
        self.assertTrue(
            any(event.event_type == EventType.AI_CALL_FAILED for event in event_store.events)
        )

    def test_times_out_and_fails_job(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        payload_store = self._build_payload_store()
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
            idempotency_key="idem_timeout_123",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
            document_text="contract body",
        )
        failed = runner.execute(job.job_id)

        self.assertEqual(failed.status, JobStatus.FAILED)
        self.assertEqual(failed.error_code, "timeout")
        self.assertEqual(event_store.events[-1].event_type, EventType.JOB_FAILED)

    def test_get_job_status_reads_saved_job(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        enqueue = EnqueueDocumentAnalysisJob(job_store=job_store, event_store=event_store)
        job = enqueue.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_status_123",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
        )

        fetched = GetJobStatus(job_store=job_store).execute(job_id=job.job_id)
        self.assertEqual(fetched.job_id, job.job_id)

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
            [EventType.JOB_STARTED, EventType.JOB_STATUS_UPDATED, EventType.JOB_COMPLETED],
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
