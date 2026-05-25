from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field
from threading import RLock

from new_era.application.ports import JobStore
from new_era.domain.jobs import JobRecord, JobStatus, JobType


@dataclass(slots=True)
class InMemoryJobStore(JobStore):
    jobs: dict[str, JobRecord] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def save(self, job: JobRecord) -> None:
        with self._lock:
            self.jobs[job.job_id] = job

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self.jobs.get(job_id)

    def update(self, job: JobRecord) -> None:
        with self._lock:
            self.jobs[job.job_id] = job

    def find_by_idempotency_key(
        self,
        *,
        job_type: JobType,
        user_id: str,
        session_id: str,
        idempotency_key: str,
    ) -> JobRecord | None:
        with self._lock:
            for job in self.jobs.values():
                if (
                    job.job_type == job_type
                    and job.user_id == user_id
                    and job.session_id == session_id
                    and job.idempotency_key == idempotency_key
                ):
                    return job
        return None

    def list_by_session(
        self,
        *,
        user_id: str,
        session_id: str,
        module: str | None = None,
        status: JobStatus | None = None,
        limit: int | None = None,
    ) -> list[JobRecord]:
        with self._lock:
            jobs = [
                job
                for job in self.jobs.values()
                if job.user_id == user_id
                and job.session_id == session_id
                and (module is None or job.module == module)
                and (status is None or job.status == status)
            ]
        jobs.sort(key=lambda job: (job.created_at, job.job_id), reverse=True)
        return jobs[:limit] if limit is not None else jobs

    def count_by_session_statuses(
        self,
        *,
        user_id: str,
        session_id: str,
        statuses: Collection[JobStatus],
        module: str | None = None,
    ) -> int:
        wanted_statuses = set(statuses)
        if not wanted_statuses:
            return 0
        with self._lock:
            return sum(
                1
                for job in self.jobs.values()
                if job.user_id == user_id
                and job.session_id == session_id
                and job.status in wanted_statuses
                and (module is None or job.module == module)
            )
