from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobType(StrEnum):
    DOCUMENT_CONTRACT_ANALYSIS = "document_contract_analysis"


@dataclass(frozen=True, slots=True)
class JobExecutionPolicy:
    max_attempts: int = 1
    timeout_seconds: float = 30.0
    retry_backoff_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class JobRecord:
    job_type: JobType
    user_id: str
    session_id: str
    module: str
    idempotency_key: str
    max_attempts: int
    timeout_seconds: float
    retry_backoff_seconds: float
    metadata: dict[str, object] = field(default_factory=dict)
    job_id: str = field(default_factory=lambda: f"job_{uuid4().hex}")
    status: JobStatus = JobStatus.QUEUED
    attempts: int = 0
    result_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type.value,
            "status": self.status.value,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "module": self.module,
            "idempotency_key": self.idempotency_key,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "timeout_seconds": self.timeout_seconds,
            "retry_backoff_seconds": self.retry_backoff_seconds,
            "result_id": self.result_id,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": dict(self.metadata),
        }
