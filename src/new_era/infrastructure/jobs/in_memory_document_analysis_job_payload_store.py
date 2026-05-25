from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from new_era.application.ports.document_analysis_job_payload_store import (
    DocumentAnalysisJobPayload,
    DocumentAnalysisJobPayloadStore,
)


@dataclass(slots=True)
class InMemoryDocumentAnalysisJobPayloadStore(DocumentAnalysisJobPayloadStore):
    payloads: dict[str, DocumentAnalysisJobPayload] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def save(self, payload: DocumentAnalysisJobPayload) -> None:
        with self._lock:
            self.payloads[payload.job_id] = payload

    def get(self, job_id: str) -> DocumentAnalysisJobPayload | None:
        with self._lock:
            return self.payloads.get(job_id)

    def delete(self, job_id: str) -> None:
        with self._lock:
            self.payloads.pop(job_id, None)
