from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from new_era.application.ports import EventStore, JobStore
from new_era.domain.events import Event, EventType
from new_era.domain.jobs import JobRecord, JobStatus, JobType


@dataclass(frozen=True, slots=True)
class EnqueueDocumentAnalysisJob:
    job_store: JobStore
    event_store: EventStore

    def execute(
        self,
        *,
        user_id: str,
        session_id: str,
        idempotency_key: str,
        correlation_id: str,
        trace_id: str,
        artifact_label: str,
        source_type: str,
    ) -> JobRecord:
        existing_job = self.job_store.find_by_idempotency_key(
            job_type=JobType.DOCUMENT_CONTRACT_ANALYSIS,
            user_id=user_id,
            session_id=session_id,
            idempotency_key=idempotency_key,
        )
        if existing_job is not None:
            return existing_job

        job = JobRecord(
            job_type=JobType.DOCUMENT_CONTRACT_ANALYSIS,
            user_id=user_id,
            session_id=session_id,
            module="documents",
            idempotency_key=idempotency_key,
            metadata={
                "artifact_label": artifact_label,
                "source_type": source_type,
            },
        )
        self.job_store.save(job)
        self.event_store.append(
            Event(
                event_type=EventType.JOB_STARTED,
                user_id=user_id,
                session_id=session_id,
                module="documents",
                correlation_id=correlation_id,
                trace_id=trace_id,
                metadata={
                    "job_id": job.job_id,
                    "job_type": job.job_type.value,
                    "artifact_label": artifact_label,
                    "source_type": source_type,
                },
            )
        )
        return job


@dataclass(frozen=True, slots=True)
class GetJobStatus:
    job_store: JobStore

    def execute(self, *, job_id: str) -> JobRecord | None:
        return self.job_store.get(job_id)


@dataclass(frozen=True, slots=True)
class AdvanceDocumentAnalysisJob:
    job_store: JobStore
    event_store: EventStore

    def execute(
        self,
        *,
        job_id: str,
        target_status: JobStatus,
        correlation_id: str,
        trace_id: str,
    ) -> JobRecord | None:
        existing_job = self.job_store.get(job_id)
        if existing_job is None:
            return None

        self._validate_transition(existing_job.status, target_status)
        updated_job = replace(
            existing_job,
            status=target_status,
            updated_at=datetime.now(UTC),
        )
        self.job_store.update(updated_job)
        self.event_store.append(
            Event(
                event_type=self._event_type_for(target_status),
                user_id=updated_job.user_id,
                session_id=updated_job.session_id,
                module=updated_job.module,
                correlation_id=correlation_id,
                trace_id=trace_id,
                metadata={
                    "job_id": updated_job.job_id,
                    "job_type": updated_job.job_type.value,
                    "from_status": existing_job.status.value,
                    "to_status": updated_job.status.value,
                },
            )
        )
        return updated_job

    def _validate_transition(self, current_status: JobStatus, target_status: JobStatus) -> None:
        allowed_transitions = {
            JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.FAILED},
            JobStatus.RUNNING: {JobStatus.SUCCEEDED, JobStatus.FAILED},
            JobStatus.SUCCEEDED: set(),
            JobStatus.FAILED: set(),
        }
        if target_status == current_status:
            return
        if target_status not in allowed_transitions[current_status]:
            raise ValueError(
                f"invalid job transition from {current_status.value} to {target_status.value}"
            )

    def _event_type_for(self, status: JobStatus) -> EventType:
        if status == JobStatus.RUNNING:
            return EventType.JOB_STATUS_UPDATED
        if status == JobStatus.SUCCEEDED:
            return EventType.JOB_COMPLETED
        if status == JobStatus.FAILED:
            return EventType.JOB_FAILED
        return EventType.JOB_STATUS_UPDATED
