from __future__ import annotations

from dataclasses import dataclass, field

from new_era.application.ports import JobStore
from new_era.domain.jobs import JobRecord, JobType


@dataclass(slots=True)
class InMemoryJobStore(JobStore):
    jobs: dict[str, JobRecord] = field(default_factory=dict)

    def save(self, job: JobRecord) -> None:
        self.jobs[job.job_id] = job

    def get(self, job_id: str) -> JobRecord | None:
        return self.jobs.get(job_id)

    def update(self, job: JobRecord) -> None:
        self.jobs[job.job_id] = job

    def find_by_idempotency_key(
        self,
        *,
        job_type: JobType,
        user_id: str,
        session_id: str,
        idempotency_key: str,
    ) -> JobRecord | None:
        for job in self.jobs.values():
            if (
                job.job_type == job_type
                and job.user_id == user_id
                and job.session_id == session_id
                and job.idempotency_key == idempotency_key
            ):
                return job
        return None
