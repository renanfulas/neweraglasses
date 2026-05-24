from __future__ import annotations

import re
from dataclasses import dataclass

from new_era.domain.documents.models import (
    ContractFinding,
    ContractFindingType,
    ContractReviewAnalysis,
)


@dataclass(frozen=True, slots=True)
class FindingRule:
    finding_type: ContractFindingType
    label: str
    patterns: tuple[str, ...]
    weight: float


FINDING_RULES: tuple[FindingRule, ...] = (
    FindingRule(
        finding_type=ContractFindingType.AUTOMATIC_RENEWAL,
        label="automatic renewal",
        patterns=(
            r"renovacao automatica",
            r"renovacao\s+por\s+igual\s+periodo",
            r"automatic renewal",
            r"automatically renew",
        ),
        weight=0.34,
    ),
    FindingRule(
        finding_type=ContractFindingType.CANCELLATION_FEE,
        label="cancellation fee",
        patterns=(
            r"multa de cancelamento",
            r"multa por cancelamento",
            r"cancellation fee",
            r"termination fee",
        ),
        weight=0.28,
    ),
    FindingRule(
        finding_type=ContractFindingType.MINIMUM_COMMITMENT,
        label="minimum commitment",
        patterns=(
            r"fidelidade",
            r"prazo minimo",
            r"12 meses",
            r"minimum term",
        ),
        weight=0.22,
    ),
    FindingRule(
        finding_type=ContractFindingType.FEES_OR_INTEREST,
        label="fees or interest",
        patterns=(
            r"juros",
            r"taxa de atraso",
            r"late fee",
            r"interest rate",
        ),
        weight=0.16,
    ),
)


@dataclass(frozen=True, slots=True)
class DeterministicContractAnalyzer:
    excerpt_radius: int = 90

    def analyze(self, *, document_text: str, source_confidence: float) -> ContractReviewAnalysis:
        sanitized_text = self._sanitize_text(document_text)
        normalized_text = sanitized_text.lower()
        findings: list[ContractFinding] = []
        parsing_notes: list[str] = []
        combined_weight = 0.0

        if len(sanitized_text) < 24:
            parsing_notes.append("limited_text_available")

        for rule in FINDING_RULES:
            match = self._first_match(normalized_text, rule.patterns)
            if match is None:
                continue

            excerpt = self._extract_excerpt(sanitized_text, match.start(), match.end())
            finding_confidence = round(min(0.98, source_confidence * (0.72 + rule.weight)), 2)
            findings.append(
                ContractFinding(
                    finding_type=rule.finding_type,
                    label=rule.label,
                    excerpt=excerpt,
                    confidence=finding_confidence,
                )
            )
            combined_weight += rule.weight

        if not findings:
            summary_title = "No contract risk signal found"
            summary_body = (
                "No known renewal, cancellation, or fee pattern was detected in the visible text. "
                "A clearer capture may reveal more detail."
            )
            review_confidence = round(max(0.18, min(source_confidence * 0.45, 0.44)), 2)
        else:
            top_labels = ", ".join(finding.label for finding in findings[:2])
            summary_title = "Contract clause needs attention"
            summary_body = (
                f"Possible {top_labels}. This clause deserves review before signing."
            )
            excerpt_bonus = 0.08 if all(finding.excerpt for finding in findings) else 0.0
            review_confidence = round(
                min(0.99, (0.28 + combined_weight + excerpt_bonus) * (0.62 + 0.38 * source_confidence)),
                2,
            )

        return ContractReviewAnalysis(
            extracted_text=sanitized_text,
            source_confidence=round(source_confidence, 2),
            review_confidence=review_confidence,
            summary_title=summary_title,
            summary_body=summary_body,
            findings=tuple(findings),
            parsing_notes=tuple(parsing_notes),
        )

    def _sanitize_text(self, document_text: str) -> str:
        cleaned = re.sub(r"\s+", " ", document_text).strip()
        return cleaned

    def _first_match(self, normalized_text: str, patterns: tuple[str, ...]) -> re.Match[str] | None:
        for pattern in patterns:
            match = re.search(pattern, normalized_text)
            if match is not None:
                return match
        return None

    def _extract_excerpt(self, document_text: str, start: int, end: int) -> str:
        excerpt_start = max(start - self.excerpt_radius, 0)
        excerpt_end = min(end + self.excerpt_radius, len(document_text))
        excerpt = document_text[excerpt_start:excerpt_end].strip(" .,;:\n")
        return excerpt
