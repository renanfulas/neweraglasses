from __future__ import annotations

from dataclasses import dataclass

from new_era.application.ports import ObservationInterpreter
from new_era.domain.attention import AlertCandidate, AlertPriority
from new_era.domain.observations import Observation, ObservationKind


@dataclass(frozen=True, slots=True)
class SimpleSimulationObservationAdapter(ObservationInterpreter):
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
            metadata={
                "observation_id": observation.observation_id,
                "item_name": item_name,
            },
        )

    def _to_document_candidate(self, observation: Observation) -> AlertCandidate | None:
        document_text = str(observation.metadata.get("document_text", ""))
        confidence = float(observation.metadata.get("confidence", 0.9))
        normalized_text = document_text.lower()
        risk_signals: list[str] = []

        if any(term in normalized_text for term in ("renovação automática", "renovacao automatica", "automatic renewal", "automatically renew")):
            risk_signals.append("automatic renewal")
        if any(term in normalized_text for term in ("multa de cancelamento", "cancellation fee", "termination fee")):
            risk_signals.append("cancellation fee")
        if any(term in normalized_text for term in ("fidelidade", "minimum term", "12 months")):
            risk_signals.append("minimum commitment")
        if any(term in normalized_text for term in ("juros", "interest rate", "late fee")):
            risk_signals.append("fees or interest")

        if not risk_signals:
            return None

        body_signals = ", ".join(risk_signals[:2])
        return AlertCandidate(
            candidate_id=f"candidate_{observation.observation_id}",
            user_id=observation.user_id,
            session_id=observation.session_id,
            module=observation.module,
            alert_type=observation.kind.value,
            title="Contract clause needs attention",
            body=f"Possible {body_signals}. Review the clause before signing.",
            priority=AlertPriority.HIGH,
            confidence=confidence,
            category="documents",
            metadata={
                "observation_id": observation.observation_id,
                "risk_signals": tuple(risk_signals),
            },
        )
