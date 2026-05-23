from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from new_era.application.use_cases.deliver_lens_command import DeliverLensCommand
from new_era.application.use_cases.evaluate_alert_candidate import EvaluateAlertCandidate
from new_era.domain.attention import AlertCandidate, AttentionMode
from new_era.domain.events import EventType
from new_era.domain.lens import LensCommand


class AlertProcessingOutcome(StrEnum):
    DELIVERED = "delivered"
    SUPPRESSED = "suppressed"
    DELIVERY_SKIPPED = "delivery_skipped"


@dataclass(frozen=True, slots=True)
class AlertProcessingResult:
    outcome: AlertProcessingOutcome
    command: LensCommand | None


@dataclass(frozen=True, slots=True)
class ProcessAlertCandidate:
    evaluator: EvaluateAlertCandidate
    delivery: DeliverLensCommand

    def execute(
        self,
        candidate: AlertCandidate,
        mode: AttentionMode,
        recent_category_count: int,
        correlation_id: str,
        trace_id: str,
    ) -> AlertProcessingResult:
        command = self.evaluator.execute(
            candidate=candidate,
            mode=mode,
            recent_category_count=recent_category_count,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )

        if command is None:
            return AlertProcessingResult(
                outcome=AlertProcessingOutcome.SUPPRESSED,
                command=None,
            )

        before_delivery_count = len(self.delivery.event_store.events)
        self.delivery.execute(
            command=command,
            user_id=candidate.user_id,
            session_id=candidate.session_id,
            module=candidate.module,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )
        delivery_events = self.delivery.event_store.events[before_delivery_count:]
        if any(event.event_type == EventType.LENS_COMMAND_DELIVERED for event in delivery_events):
            return AlertProcessingResult(
                outcome=AlertProcessingOutcome.DELIVERED,
                command=command,
            )

        return AlertProcessingResult(
            outcome=AlertProcessingOutcome.DELIVERY_SKIPPED,
            command=command,
        )
