from unittest import TestCase

from new_era.application.use_cases import (
    AdvanceDocumentAnalysisJob,
    EnqueueDocumentAnalysisJob,
    GetJobStatus,
)
from new_era.domain.events import EventType
from new_era.domain.jobs import JobStatus
from new_era.infrastructure.events import InMemoryEventStore
from new_era.infrastructure.jobs import InMemoryJobStore


class DocumentAnalysisJobsTest(TestCase):
    def test_enqueues_document_analysis_job_and_records_event(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        use_case = EnqueueDocumentAnalysisJob(job_store=job_store, event_store=event_store)

        job = use_case.execute(
            user_id="user_1",
            session_id="session_1",
            idempotency_key="idem_12345678",
            correlation_id="corr_1",
            trace_id="trace_1",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
        )

        self.assertEqual(job.status.value, "queued")
        self.assertEqual(job_store.get(job.job_id), job)
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

    def test_advances_job_through_running_and_succeeded(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        enqueue = EnqueueDocumentAnalysisJob(job_store=job_store, event_store=event_store)
        advance = AdvanceDocumentAnalysisJob(job_store=job_store, event_store=event_store)
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
        )

        self.assertEqual(running_job.status, JobStatus.RUNNING)
        self.assertEqual(succeeded_job.status, JobStatus.SUCCEEDED)
        self.assertEqual(
            [event.event_type for event in event_store.events],
            [
                EventType.JOB_STARTED,
                EventType.JOB_STATUS_UPDATED,
                EventType.JOB_COMPLETED,
            ],
        )

    def test_rejects_invalid_job_transition(self) -> None:
        job_store = InMemoryJobStore()
        event_store = InMemoryEventStore()
        enqueue = EnqueueDocumentAnalysisJob(job_store=job_store, event_store=event_store)
        advance = AdvanceDocumentAnalysisJob(job_store=job_store, event_store=event_store)
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
