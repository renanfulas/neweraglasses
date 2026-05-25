from __future__ import annotations

from typing import Protocol

from new_era.domain.jobs import JobRecord, JobType


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
