from __future__ import annotations

from dataclasses import dataclass

from new_era.application.ports import EventStore, ObservationInterpreter
from new_era.application.use_cases.process_alert_candidate import (
    AlertProcessingOutcome,
    AlertProcessingResult,
    ProcessAlertCandidate,
)
from new_era.domain.attention import AttentionMode
from new_era.domain.events import Event, EventType
from new_era.domain.observations import Observation


@dataclass(frozen=True, slots=True)
class ObservationProcessingResult:
    outcome: AlertProcessingOutcome
    candidate_created: bool
    alert_result: AlertProcessingResult | None


@dataclass(frozen=True, slots=True)
class ProcessObservation:
    observation_interpreter: ObservationInterpreter
    alert_processor: ProcessAlertCandidate
    event_store: EventStore

    def execute(
        self,
        observation: Observation,
        mode: AttentionMode,
        recent_category_count: int,
        correlation_id: str,
        trace_id: str,
    ) -> ObservationProcessingResult:
        self.event_store.append(
            Event(
                event_type=EventType.OBSERVATION_CREATED,
                user_id=observation.user_id,
                session_id=observation.session_id,
                module=observation.module,
                correlation_id=correlation_id,
                trace_id=trace_id,
                metadata={
                    "observation_id": observation.observation_id,
                    "kind": observation.kind.value,
                    "summary": observation.summary,
                },
            )
        )

        candidate = self.observation_interpreter.to_alert_candidate(observation)
        if candidate is None:
            return ObservationProcessingResult(
                outcome=AlertProcessingOutcome.SUPPRESSED,
                candidate_created=False,
                alert_result=None,
            )

        alert_result = self.alert_processor.execute(
            candidate=candidate,
            mode=mode,
            recent_category_count=recent_category_count,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )
        return ObservationProcessingResult(
            outcome=alert_result.outcome,
            candidate_created=True,
            alert_result=alert_result,
        )
