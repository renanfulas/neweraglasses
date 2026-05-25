from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from time import sleep
from typing import Protocol
from uuid import uuid4

from new_era.application.ports import (
    DocumentAnalysisJobPayload,
    DocumentAnalysisJobPayloadStore,
    DocumentAnalysisStore,
    EventStore,
    JobStore,
)
from new_era.domain.attention import AttentionMode
from new_era.domain.documents import DocumentAnalysisRecord
from new_era.domain.events import Event, EventType
from new_era.domain.jobs import JobExecutionPolicy, JobRecord, JobStatus, JobType


class DocumentContractReviewResultLike(Protocol):
    analysis_record: DocumentAnalysisRecord


class DocumentContractReviewProcessor(Protocol):
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
    ) -> DocumentContractReviewResultLike:
        raise NotImplementedError


class DocumentAnalysisJobTimedOut(TimeoutError):
    pass


@dataclass(frozen=True, slots=True)
class EnqueueDocumentAnalysisJob:
    job_store: JobStore
    event_store: EventStore
    payload_store: DocumentAnalysisJobPayloadStore | None = None
    execution_policy: JobExecutionPolicy = JobExecutionPolicy()

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
        document_text: str | None = None,
        document_image_base64: str | None = None,
        confidence: float | None = 0.92,
        mode: AttentionMode = AttentionMode.BALANCED,
        recent_category_count: int = 0,
        observation_id: str | None = None,
    ) -> JobRecord:
        existing_job = self.job_store.find_by_idempotency_key(
            job_type=JobType.DOCUMENT_CONTRACT_ANALYSIS,
            user_id=user_id,
            session_id=session_id,
            idempotency_key=idempotency_key,
        )
        if existing_job is not None:
            self._save_payload_if_needed(
                job=existing_job,
                user_id=user_id,
                session_id=session_id,
                artifact_label=artifact_label,
                source_type=source_type,
                document_text=document_text,
                document_image_base64=document_image_base64,
                confidence=confidence,
                mode=mode,
                recent_category_count=recent_category_count,
                observation_id=observation_id,
                correlation_id=correlation_id,
                trace_id=trace_id,
            )
            return existing_job

        job = JobRecord(
            job_type=JobType.DOCUMENT_CONTRACT_ANALYSIS,
            user_id=user_id,
            session_id=session_id,
            module="documents",
            idempotency_key=idempotency_key,
            max_attempts=self.execution_policy.max_attempts,
            timeout_seconds=self.execution_policy.timeout_seconds,
            retry_backoff_seconds=self.execution_policy.retry_backoff_seconds,
            metadata={
                "artifact_label": artifact_label,
                "source_type": source_type,
            },
        )
        self.job_store.save(job)
        self._save_payload_if_needed(
            job=job,
            user_id=user_id,
            session_id=session_id,
            artifact_label=artifact_label,
            source_type=source_type,
            document_text=document_text,
            document_image_base64=document_image_base64,
            confidence=confidence,
            mode=mode,
            recent_category_count=recent_category_count,
            observation_id=observation_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )
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
                    "max_attempts": job.max_attempts,
                    "timeout_seconds": job.timeout_seconds,
                },
            )
        )
        return job

    def _save_payload_if_needed(
        self,
        *,
        job: JobRecord,
        user_id: str,
        session_id: str,
        artifact_label: str,
        source_type: str,
        document_text: str | None,
        document_image_base64: str | None,
        confidence: float | None,
        mode: AttentionMode,
        recent_category_count: int,
        observation_id: str | None,
        correlation_id: str,
        trace_id: str,
    ) -> None:
        if self.payload_store is None or not (document_text or document_image_base64):
            return
        if self.payload_store.get(job.job_id) is not None:
            return
        self.payload_store.save(
            DocumentAnalysisJobPayload(
                job_id=job.job_id,
                user_id=user_id,
                session_id=session_id,
                artifact_label=artifact_label,
                source_type=source_type,
                document_text=document_text,
                document_image_base64=document_image_base64,
                confidence=confidence,
                mode=mode,
                recent_category_count=recent_category_count,
                observation_id=observation_id,
                correlation_id=correlation_id,
                trace_id=trace_id,
            )
        )


@dataclass(frozen=True, slots=True)
class GetJobStatus:
    job_store: JobStore

    def execute(self, *, job_id: str) -> JobRecord | None:
        return self.job_store.get(job_id)


@dataclass(frozen=True, slots=True)
class AdvanceDocumentAnalysisJob:
    job_store: JobStore
    event_store: EventStore
    document_analysis_store: DocumentAnalysisStore

    def execute(
        self,
        *,
        job_id: str,
        target_status: JobStatus,
        correlation_id: str,
        trace_id: str,
        analysis_id: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> JobRecord | None:
        existing_job = self.job_store.get(job_id)
        if existing_job is None:
            return None

        if target_status == existing_job.status:
            return existing_job

        self._validate_transition(existing_job.status, target_status)
        metadata = dict(existing_job.metadata)
        if target_status == JobStatus.SUCCEEDED:
            persisted_analysis = self._require_persisted_analysis(
                analysis_id=analysis_id,
                existing_job=existing_job,
            )
            metadata["analysis_id"] = persisted_analysis.analysis_id
        if target_status == JobStatus.FAILED:
            metadata["error_code"] = error_code or "manual_failure"

        updated_job = replace(
            existing_job,
            status=target_status,
            metadata=metadata,
            result_id=metadata.get("analysis_id") if target_status == JobStatus.SUCCEEDED else None,
            error_code=error_code if target_status == JobStatus.FAILED else None,
            error_message=error_message if target_status == JobStatus.FAILED else None,
            updated_at=datetime.now(UTC),
            completed_at=datetime.now(UTC)
            if target_status in (JobStatus.SUCCEEDED, JobStatus.FAILED)
            else existing_job.completed_at,
        )
        self.job_store.update(updated_job)
        event_metadata = {
            "job_id": updated_job.job_id,
            "job_type": updated_job.job_type.value,
            "from_status": existing_job.status.value,
            "to_status": updated_job.status.value,
        }
        if target_status == JobStatus.SUCCEEDED:
            event_metadata["analysis_id"] = metadata["analysis_id"]
        if target_status == JobStatus.FAILED:
            event_metadata["error_code"] = updated_job.error_code or "manual_failure"
        self.event_store.append(
            Event(
                event_type=self._event_type_for(target_status),
                user_id=updated_job.user_id,
                session_id=updated_job.session_id,
                module=updated_job.module,
                correlation_id=correlation_id,
                trace_id=trace_id,
                metadata=event_metadata,
            )
        )
        return updated_job

    def _require_persisted_analysis(
        self,
        *,
        analysis_id: str | None,
        existing_job: JobRecord,
    ):
        if not analysis_id:
            raise ValueError("analysis_id is required when completing document analysis jobs")
        persisted_analysis = self.document_analysis_store.get(analysis_id)
        if persisted_analysis is None:
            raise ValueError("document analysis not found for provided analysis_id")
        if persisted_analysis.session_id != existing_job.session_id:
            raise ValueError("analysis_id does not belong to the same session as the job")
        if persisted_analysis.user_id != existing_job.user_id:
            raise ValueError("analysis_id does not belong to the same user as the job")
        return persisted_analysis

    def _validate_transition(self, current_status: JobStatus, target_status: JobStatus) -> None:
        allowed_transitions = {
            JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.FAILED},
            JobStatus.RUNNING: {JobStatus.SUCCEEDED, JobStatus.FAILED},
            JobStatus.SUCCEEDED: set(),
            JobStatus.FAILED: set(),
        }
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


@dataclass(frozen=True, slots=True)
class RunDocumentAnalysisJob:
    job_store: JobStore
    event_store: EventStore
    payload_store: DocumentAnalysisJobPayloadStore
    document_processor: DocumentContractReviewProcessor

    def execute(self, *, job_id: str) -> JobRecord | None:
        job = self.job_store.get(job_id)
        if job is None:
            return None
        if job.status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
            return job

        payload = self.payload_store.get(job_id)
        if payload is None or not payload.has_document_input:
            return self._fail_job(
                job=job,
                correlation_id=f"corr_{uuid4().hex}",
                trace_id=f"trace_{uuid4().hex}",
                error_code="missing_document_payload",
                error_message="document_text_or_document_image_base64_required",
            )

        while True:
            current_job = self.job_store.get(job_id)
            if current_job is None:
                return None
            if current_job.status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
                return current_job
            if current_job.attempts >= current_job.max_attempts:
                return self._fail_job(
                    job=current_job,
                    correlation_id=payload.correlation_id,
                    trace_id=payload.trace_id,
                    error_code=current_job.error_code or "max_attempts_exhausted",
                    error_message=current_job.error_message or "job attempts exhausted",
                )

            attempt = current_job.attempts + 1
            running_job = self._start_attempt(
                job=current_job,
                attempt=attempt,
                correlation_id=payload.correlation_id,
                trace_id=payload.trace_id,
            )

            try:
                result = self._process_with_timeout(payload=payload, attempt=attempt, job=running_job)
            except DocumentAnalysisJobTimedOut as exc:
                failed_attempt_job = self._record_attempt_failure(
                    job=running_job,
                    correlation_id=payload.correlation_id,
                    trace_id=payload.trace_id,
                    error_code="timeout",
                    error_message=str(exc),
                )
            except Exception as exc:
                failed_attempt_job = self._record_attempt_failure(
                    job=running_job,
                    correlation_id=payload.correlation_id,
                    trace_id=payload.trace_id,
                    error_code="execution_error",
                    error_message=str(exc) or exc.__class__.__name__,
                )
            else:
                self.payload_store.delete(job_id)
                return self._complete_job(
                    job=running_job,
                    correlation_id=payload.correlation_id,
                    trace_id=payload.trace_id,
                    analysis_id=result.analysis_record.analysis_id,
                )

            if failed_attempt_job.attempts >= failed_attempt_job.max_attempts:
                self.payload_store.delete(job_id)
                return self._fail_job(
                    job=failed_attempt_job,
                    correlation_id=payload.correlation_id,
                    trace_id=payload.trace_id,
                    error_code=failed_attempt_job.error_code or "execution_error",
                    error_message=failed_attempt_job.error_message or "job failed",
                )
            if failed_attempt_job.retry_backoff_seconds:
                sleep(failed_attempt_job.retry_backoff_seconds)

    def _process_with_timeout(
        self,
        *,
        payload: DocumentAnalysisJobPayload,
        attempt: int,
        job: JobRecord,
    ) -> DocumentContractReviewResultLike:
        executor = ThreadPoolExecutor(max_workers=1)
        observation_id = payload.observation_id or f"obs_{job.job_id}_{attempt}"
        future = executor.submit(
            self.document_processor.process_contract_review,
            observation_id=observation_id,
            user_id=payload.user_id,
            session_id=payload.session_id,
            document_text=payload.document_text,
            document_image_base64=payload.document_image_base64,
            confidence=payload.confidence,
            mode=payload.mode,
            recent_category_count=payload.recent_category_count,
            correlation_id=payload.correlation_id,
            trace_id=payload.trace_id,
        )
        try:
            return future.result(timeout=job.timeout_seconds)
        except FutureTimeoutError as exc:
            future.cancel()
            raise DocumentAnalysisJobTimedOut(
                f"document analysis exceeded {job.timeout_seconds:g}s timeout"
            ) from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _start_attempt(
        self,
        *,
        job: JobRecord,
        attempt: int,
        correlation_id: str,
        trace_id: str,
    ) -> JobRecord:
        now = datetime.now(UTC)
        updated_job = replace(
            job,
            status=JobStatus.RUNNING,
            attempts=attempt,
            error_code=None,
            error_message=None,
            updated_at=now,
            started_at=job.started_at or now,
        )
        self.job_store.update(updated_job)
        self._append_job_event(
            job=updated_job,
            event_type=EventType.JOB_STATUS_UPDATED,
            correlation_id=correlation_id,
            trace_id=trace_id,
            metadata={
                "from_status": job.status.value,
                "to_status": JobStatus.RUNNING.value,
                "attempt": attempt,
                "max_attempts": updated_job.max_attempts,
            },
        )
        return updated_job

    def _record_attempt_failure(
        self,
        *,
        job: JobRecord,
        correlation_id: str,
        trace_id: str,
        error_code: str,
        error_message: str,
    ) -> JobRecord:
        metadata = dict(job.metadata)
        metadata.update(
            {
                "last_error_code": error_code,
                "retry_scheduled": job.attempts < job.max_attempts,
            }
        )
        updated_job = replace(
            job,
            metadata=metadata,
            error_code=error_code,
            error_message=error_message,
            updated_at=datetime.now(UTC),
        )
        self.job_store.update(updated_job)
        self._append_job_event(
            job=updated_job,
            event_type=EventType.AI_CALL_FAILED,
            correlation_id=correlation_id,
            trace_id=trace_id,
            metadata={
                "attempt": updated_job.attempts,
                "max_attempts": updated_job.max_attempts,
                "error_code": error_code,
                "retry_scheduled": updated_job.attempts < updated_job.max_attempts,
            },
        )
        if updated_job.attempts < updated_job.max_attempts:
            self._append_job_event(
                job=updated_job,
                event_type=EventType.JOB_STATUS_UPDATED,
                correlation_id=correlation_id,
                trace_id=trace_id,
                metadata={
                    "from_status": JobStatus.RUNNING.value,
                    "to_status": JobStatus.RUNNING.value,
                    "attempt": updated_job.attempts,
                    "retry_scheduled": True,
                    "error_code": error_code,
                },
            )
        return updated_job

    def _complete_job(
        self,
        *,
        job: JobRecord,
        correlation_id: str,
        trace_id: str,
        analysis_id: str,
    ) -> JobRecord:
        metadata = dict(job.metadata)
        metadata["analysis_id"] = analysis_id
        updated_job = replace(
            job,
            status=JobStatus.SUCCEEDED,
            metadata=metadata,
            result_id=analysis_id,
            error_code=None,
            error_message=None,
            updated_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        self.job_store.update(updated_job)
        self._append_job_event(
            job=updated_job,
            event_type=EventType.JOB_COMPLETED,
            correlation_id=correlation_id,
            trace_id=trace_id,
            metadata={
                "from_status": JobStatus.RUNNING.value,
                "to_status": JobStatus.SUCCEEDED.value,
                "attempt": updated_job.attempts,
                "analysis_id": analysis_id,
            },
        )
        return updated_job

    def _fail_job(
        self,
        *,
        job: JobRecord,
        correlation_id: str,
        trace_id: str,
        error_code: str,
        error_message: str,
    ) -> JobRecord:
        metadata = dict(job.metadata)
        metadata.update(
            {
                "error_code": error_code,
                "retry_scheduled": False,
            }
        )
        updated_job = replace(
            job,
            status=JobStatus.FAILED,
            metadata=metadata,
            error_code=error_code,
            error_message=error_message,
            updated_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        self.job_store.update(updated_job)
        self._append_job_event(
            job=updated_job,
            event_type=EventType.JOB_FAILED,
            correlation_id=correlation_id,
            trace_id=trace_id,
            metadata={
                "from_status": job.status.value,
                "to_status": JobStatus.FAILED.value,
                "attempt": updated_job.attempts,
                "max_attempts": updated_job.max_attempts,
                "error_code": error_code,
            },
        )
        return updated_job

    def _append_job_event(
        self,
        *,
        job: JobRecord,
        event_type: EventType,
        correlation_id: str,
        trace_id: str,
        metadata: dict[str, object],
    ) -> None:
        self.event_store.append(
            Event(
                event_type=event_type,
                user_id=job.user_id,
                session_id=job.session_id,
                module=job.module,
                correlation_id=correlation_id,
                trace_id=trace_id,
                metadata={
                    "job_id": job.job_id,
                    "job_type": job.job_type.value,
                    **metadata,
                },
            )
        )
