from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping
from uuid import uuid4


class JobType(StrEnum):
    DOCUMENT_CONTRACT_ANALYSIS = "document_contract_analysis"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class JobRecord:
    job_type: JobType
    user_id: str
    session_id: str
    module: str
    idempotency_key: str
    metadata: Mapping[str, object] = field(default_factory=dict)
    job_id: str = field(default_factory=lambda: f"job_{uuid4().hex}")
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type.value,
            "status": self.status.value,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "module": self.module,
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": dict(self.metadata),
        }
