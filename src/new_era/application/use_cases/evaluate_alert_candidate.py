from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from new_era.application.ports.event_store import EventStore
from new_era.domain.attention.models import AlertCandidate, AttentionMode
from new_era.domain.attention.policy import AttentionPolicy
from new_era.domain.events.models import Event, EventType
from new_era.domain.lens.models import LensCommand, LensCommandType


@dataclass(frozen=True, slots=True)
class EvaluateAlertCandidate:
    attention_policy: AttentionPolicy
    event_store: EventStore

    def execute(
        self,
        candidate: AlertCandidate,
        mode: AttentionMode,
        recent_category_count: int,
        correlation_id: str,
        trace_id: str,
    ) -> LensCommand | None:
        self.event_store.append(
            Event(
                event_type=EventType.ALERT_CANDIDATE_CREATED,
                user_id=candidate.user_id,
                session_id=candidate.session_id,
                module=candidate.module,
                correlation_id=correlation_id,
                trace_id=trace_id,
                policy_version=self.attention_policy.policy_version,
                metadata={
                    "candidate_id": candidate.candidate_id,
                    "alert_type": candidate.alert_type,
                    "category": candidate.category,
                    "priority": candidate.priority.value,
                    "confidence": candidate.confidence,
                },
            )
        )

        decision = self.attention_policy.evaluate(
            candidate=candidate,
            mode=mode,
            recent_category_count=recent_category_count,
        )

        if not decision.allows_display:
            self.event_store.append(
                Event(
                    event_type=EventType.ALERT_SUPPRESSED,
                    user_id=candidate.user_id,
                    session_id=candidate.session_id,
                    module=candidate.module,
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    policy_version=self.attention_policy.policy_version,
                    metadata={
                        "candidate_id": candidate.candidate_id,
                        "decision_id": decision.decision_id,
                        "outcome": decision.outcome.value,
                        "reason": decision.reason,
                    },
                )
            )
            return None

        command = LensCommand(
            command_id=f"cmd_{uuid4().hex}",
            command_version=1,
            command_type=LensCommandType.SHOW_ALERT,
            priority=candidate.priority,
            title=candidate.title,
            body=candidate.body,
            duration_ms=5000,
            metadata={
                "module": candidate.module,
                "candidate_id": candidate.candidate_id,
                "decision_id": decision.decision_id,
            },
        )

        self.event_store.append(
            Event(
                event_type=EventType.ALERT_SHOWN,
                user_id=candidate.user_id,
                session_id=candidate.session_id,
                module=candidate.module,
                correlation_id=correlation_id,
                trace_id=trace_id,
                policy_version=self.attention_policy.policy_version,
                metadata={
                    "candidate_id": candidate.candidate_id,
                    "command_id": command.command_id,
                    "decision_id": decision.decision_id,
                    "reason": decision.reason,
                },
            )
        )
        return command
