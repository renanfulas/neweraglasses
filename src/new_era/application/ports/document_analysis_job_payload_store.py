from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from new_era.domain.attention import AttentionMode


@dataclass(frozen=True, slots=True)
class DocumentAnalysisJobPayload:
    job_id: str
    user_id: str
    session_id: str
    artifact_label: str
    source_type: str
    artifact_id: str | None
    document_text: str | None
    document_image_base64: str | None
    confidence: float | None
    mode: AttentionMode
    recent_category_count: int
    observation_id: str | None
    correlation_id: str
    trace_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def has_document_input(self) -> bool:
        return bool(self.document_text or self.document_image_base64)


class DocumentAnalysisJobPayloadStore(Protocol):
    def save(self, payload: DocumentAnalysisJobPayload) -> None:
        raise NotImplementedError

    def get(self, job_id: str) -> DocumentAnalysisJobPayload | None:
        raise NotImplementedError

    def delete(self, job_id: str) -> None:
        raise NotImplementedError
