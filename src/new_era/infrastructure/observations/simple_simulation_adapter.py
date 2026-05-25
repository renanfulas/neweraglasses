from __future__ import annotations

from dataclasses import dataclass

from new_era.application.ports import ObservationInterpreter
from new_era.domain.attention import AlertCandidate, AlertPriority
from new_era.domain.documents import (
    ContractFinding,
    ContractFindingType,
    ContractReviewAnalysis,
    DeterministicContractAnalyzer,
)
from new_era.domain.observations import Observation, ObservationKind


@dataclass(frozen=True, slots=True)
class SimpleSimulationObservationAdapter(ObservationInterpreter):
    contract_analyzer: DeterministicContractAnalyzer = DeterministicContractAnalyzer()

    def to_alert_candidate(self, observation: Observation) -> AlertCandidate | None:
        if observation.kind == ObservationKind.GROCERY_MISSING_ITEM:
            return self._to_grocery_candidate(observation)
        if observation.kind == ObservationKind.DOCUMENT_CONTRACT_REVIEW:
            return self._to_document_candidate(observation)
        return None

    def _to_grocery_candidate(self, observation: Observation) -> AlertCandidate:
        item_name = str(observation.metadata.get("item_name", "item"))
        confidence = float(observation.metadata.get("confidence", 0.9))
        title = f"Missing {item_name}"
        body = f"You still need {item_name}."
        return AlertCandidate(
            candidate_id=f"candidate_{observation.observation_id}",
            user_id=observation.user_id,
            session_id=observation.session_id,
            module=observation.module,
            alert_type=observation.kind.value,
            title=title,
            body=body,
            priority=AlertPriority.MEDIUM,
            confidence=confidence,
            category="grocery",
        )

    def _to_document_candidate(self, observation: Observation) -> AlertCandidate | None:
        analysis = self._resolve_document_analysis(observation)
        if not analysis.has_findings:
            return None

        finding_types = tuple(
            finding.finding_type.value for finding in analysis.findings[:2]
        )
        priority = (
            AlertPriority.HIGH
            if len(analysis.findings) >= 2
            else AlertPriority.MEDIUM
        )
        return AlertCandidate(
            candidate_id=f"candidate_{observation.observation_id}",
            user_id=observation.user_id,
            session_id=observation.session_id,
            module=observation.module,
            alert_type=observation.kind.value,
            title=analysis.summary_title,
            body=analysis.summary_body,
            priority=priority,
            confidence=analysis.review_confidence,
            category="documents",
        )

    def _resolve_document_analysis(
        self,
        observation: Observation,
    ) -> ContractReviewAnalysis:
        serialized_analysis = observation.metadata.get("document_analysis")
        if isinstance(serialized_analysis, dict):
            findings = tuple(
                ContractFinding(
                    finding_type=ContractFindingType(item["finding_type"]),
                    label=str(item["label"]),
                    excerpt=str(item["excerpt"]),
                    confidence=float(item["confidence"]),
                )
                for item in serialized_analysis.get("findings", [])
            )
            return ContractReviewAnalysis(
                extracted_text=str(serialized_analysis.get("extracted_text", "")),
                source_confidence=float(serialized_analysis.get("source_confidence", 0.0)),
                review_confidence=float(serialized_analysis.get("review_confidence", 0.0)),
                summary_title=str(
                    serialized_analysis.get(
                        "summary_title",
                        "Contract clause needs attention",
                    )
                ),
                summary_body=str(serialized_analysis.get("summary_body", "")),
                findings=findings,
                parsing_notes=tuple(
                    str(note) for note in serialized_analysis.get("parsing_notes", [])
                ),
            )

        fallback_text = str(observation.metadata.get("document_text", ""))
        fallback_confidence = float(observation.metadata.get("confidence", 0.9))
        return self.contract_analyzer.analyze(
            document_text=fallback_text,
            source_confidence=fallback_confidence,
        )
