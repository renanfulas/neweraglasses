from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class ContractFindingType(StrEnum):
    AUTOMATIC_RENEWAL = "automatic_renewal"
    CANCELLATION_FEE = "cancellation_fee"
    MINIMUM_COMMITMENT = "minimum_commitment"
    FEES_OR_INTEREST = "fees_or_interest"


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
        return {
            "extracted_text": self.extracted_text,
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
            "created_at": self.created_at.isoformat(),
            "analysis": self.analysis.to_dict(),
        }
