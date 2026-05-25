from __future__ import annotations

from typing import Protocol

from new_era.domain.jobs import JobRecord, JobStatus, JobType


class JobStore(Protocol):
    def save(self, job: JobRecord) -> None:
        raise NotImplementedError

    def get(self, job_id: str) -> JobRecord | None:
        raise NotImplementedError

    def update(self, job: JobRecord) -> None:
        raise NotImplementedError

    def find_by_idempotency_key(
        self,
        *,
        job_type: JobType,
        user_id: str,
        session_id: str,
        idempotency_key: str,
    ) -> JobRecord | None:
        raise NotImplementedError

    def list_by_session(
        self,
        *,
        user_id: str,
        session_id: str,
        module: str | None = None,
        status: JobStatus | None = None,
        limit: int | None = None,
    ) -> list[JobRecord]:
        raise NotImplementedError
