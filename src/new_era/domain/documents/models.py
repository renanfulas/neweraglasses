from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Mapping
from uuid import uuid4


class ContractFindingType(StrEnum):
    AUTOMATIC_RENEWAL = "automatic_renewal"
    CANCELLATION_FEE = "cancellation_fee"
    MINIMUM_COMMITMENT = "minimum_commitment"
    FEES_OR_INTEREST = "fees_or_interest"


class DocumentArtifactStatus(StrEnum):
    ACTIVE = "active"
    DELETED = "deleted"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class OCRExtraction:
    text: str
    confidence: float
    line_count: int
    engine_name: str

    def to_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "line_count": self.line_count,
            "engine_name": self.engine_name,
        }


@dataclass(frozen=True, slots=True)
class ContractFinding:
    finding_type: ContractFindingType
    label: str
    excerpt: str
    confidence: float

    def to_dict(self) -> dict[str, object]:
        return {
            "finding_type": self.finding_type.value,
            "label": self.label,
            "excerpt": self.excerpt,
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class ContractReviewAnalysis:
    extracted_text: str
    source_confidence: float
    review_confidence: float
    summary_title: str
    summary_body: str
    findings: tuple[ContractFinding, ...] = field(default_factory=tuple)
    parsing_notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_findings(self) -> bool:
        return len(self.findings) > 0

    def to_dict(self) -> dict[str, object]:
        return self.to_history_dict()

    def to_history_dict(self) -> dict[str, object]:
        return {
            "source_confidence": self.source_confidence,
            "review_confidence": self.review_confidence,
            "summary_title": self.summary_title,
            "summary_body": self.summary_body,
            "findings": [finding.to_dict() for finding in self.findings],
            "parsing_notes": list(self.parsing_notes),
        }


@dataclass(frozen=True, slots=True)
class DocumentAnalysisRecord:
    user_id: str
    session_id: str
    observation_id: str
    trace_id: str
    source_type: str
    analysis: ContractReviewAnalysis
    artifact_id: str | None = None
    analysis_id: str = field(default_factory=lambda: f"analysis_{uuid4().hex}")
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        return {
            "analysis_id": self.analysis_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "observation_id": self.observation_id,
            "trace_id": self.trace_id,
            "source_type": self.source_type,
            "artifact_id": self.artifact_id,
            "created_at": self.created_at.isoformat(),
            "analysis": self.analysis.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class DocumentArtifactRecord:
    user_id: str
    session_id: str
    artifact_label: str
    source_type: str
    content_type: str
    size_bytes: int
    storage_key: str
    local_path: str
    status: DocumentArtifactStatus = DocumentArtifactStatus.ACTIVE
    expires_at: datetime | None = None
    deleted_at: datetime | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    artifact_id: str = field(default_factory=lambda: f"artifact_{uuid4().hex}")
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.user_id:
            raise ValueError("user_id is required")
        if not self.session_id:
            raise ValueError("session_id is required")
        if not self.artifact_label:
            raise ValueError("artifact_label is required")
        if not self.source_type:
            raise ValueError("source_type is required")
        if not self.content_type:
            raise ValueError("content_type is required")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be greater than or equal to zero")
        if not self.storage_key:
            raise ValueError("storage_key is required")
        normalized_storage_key = PurePosixPath(self.storage_key)
        if normalized_storage_key.is_absolute() or ".." in normalized_storage_key.parts:
            raise ValueError("storage_key must be a safe relative path")
        if not self.local_path:
            raise ValueError("local_path is required")
        if self.status == DocumentArtifactStatus.DELETED and self.deleted_at is None:
            raise ValueError("deleted_at is required when status is deleted")
        if self.status != DocumentArtifactStatus.DELETED and self.deleted_at is not None:
            raise ValueError("deleted_at is only allowed for deleted artifacts")
        object.__setattr__(self, "storage_key", normalized_storage_key.as_posix())
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def is_active(self) -> bool:
        return self.status == DocumentArtifactStatus.ACTIVE

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "artifact_label": self.artifact_label,
            "source_type": self.source_type,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "storage_key": self.storage_key,
            "local_path": self.local_path,
            "status": self.status.value,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": dict(self.metadata),
        }
