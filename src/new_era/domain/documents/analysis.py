from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ContractFindingType(StrEnum):
    AUTOMATIC_RENEWAL = "automatic_renewal"
    PENALTY = "penalty"
    INTEREST = "interest"
    COMMITMENT = "commitment"
    CANCELLATION = "cancellation"


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
    findings: tuple[ContractFinding, ...] = ()
    parsing_notes: tuple[str, ...] = ()

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)

    @property
    def summary(self) -> str:
        return self.summary_body or self.summary_title

    @property
    def confidence(self) -> float:
        return self.review_confidence

    def to_dict(self) -> dict[str, object]:
        return {
            "extracted_text": self.extracted_text,
            "source_confidence": self.source_confidence,
            "review_confidence": self.review_confidence,
            "summary_title": self.summary_title,
            "summary_body": self.summary_body,
            "findings": [finding.to_dict() for finding in self.findings],
            "parsing_notes": list(self.parsing_notes),
            "summary": self.summary,
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class DeterministicContractAnalyzer:
    keyword_map: dict[str, str] = field(
        default_factory=lambda: {
            "renovacao automatica": "Automatic renewal clause detected.",
            "renovação automática": "Automatic renewal clause detected.",
            "multa": "Penalty clause detected.",
            "juros": "Interest clause detected.",
            "fidelidade": "Commitment period clause detected.",
            "cancelamento": "Cancellation clause detected.",
        }
    )

    def analyze(
        self,
        document_text: str,
        source_confidence: float,
    ) -> ContractReviewAnalysis:
        normalized = document_text.strip()
        lowered = normalized.lower()
        findings: list[ContractFinding] = []
        for keyword, message in self.keyword_map.items():
            if keyword not in lowered:
                continue
            findings.append(
                ContractFinding(
                    finding_type=_finding_type_for_keyword(keyword),
                    label=message,
                    excerpt=_excerpt_for_keyword(normalized, keyword),
                    confidence=max(min(source_confidence, 1.0), 0.0),
                )
            )

        if findings:
            summary_title = "Contract clause needs attention"
            summary_body = "This contract deserves attention before signing."
            review_confidence = max(min(source_confidence, 1.0), 0.0)
        elif normalized:
            summary_title = "Contract first pass complete"
            summary_body = "No obvious high-risk clause was detected in this first pass."
            review_confidence = max(min(source_confidence * 0.85, 1.0), 0.0)
        else:
            summary_title = "Contract text unavailable"
            summary_body = "No readable contract text was found."
            review_confidence = 0.0

        return ContractReviewAnalysis(
            extracted_text=normalized,
            source_confidence=max(min(source_confidence, 1.0), 0.0),
            review_confidence=review_confidence,
            summary_title=summary_title,
            summary_body=summary_body,
            findings=tuple(findings),
            parsing_notes=(),
        )


def _finding_type_for_keyword(keyword: str) -> ContractFindingType:
    if "renova" in keyword:
        return ContractFindingType.AUTOMATIC_RENEWAL
    if "multa" in keyword:
        return ContractFindingType.PENALTY
    if "juros" in keyword:
        return ContractFindingType.INTEREST
    if "fidelidade" in keyword:
        return ContractFindingType.COMMITMENT
    return ContractFindingType.CANCELLATION


def _excerpt_for_keyword(document_text: str, keyword: str) -> str:
    lowered = document_text.lower()
    index = lowered.find(keyword)
    if index < 0:
        return document_text[:160]
    start = max(index - 40, 0)
    end = min(index + len(keyword) + 80, len(document_text))
    return document_text[start:end].strip()
