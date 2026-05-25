from unittest import TestCase

from new_era.application.use_cases.evaluate_alert_candidate import EvaluateAlertCandidate
from new_era.domain.attention import (
    AlertCandidate,
    AlertPriority,
    AttentionMode,
    AttentionPolicy,
)
from new_era.domain.events import EventType
from new_era.domain.lens import LensCommandType
from new_era.infrastructure.events import InMemoryEventStore


def make_candidate(*, confidence: float = 0.9) -> AlertCandidate:
    return AlertCandidate(
        candidate_id="candidate_1",
        user_id="user_1",
        session_id="session_1",
        module="grocery",
        alert_type="missing_item",
        title="Missing item",
        body="You still need eggs.",
        priority=AlertPriority.MEDIUM,
        confidence=confidence,
        category="grocery",
    )


class EvaluateAlertCandidateTest(TestCase):
    def test_returns_lens_command_after_attention_policy_allows_display(self) -> None:
        event_store = InMemoryEventStore()
        use_case = EvaluateAlertCandidate(
            attention_policy=AttentionPolicy(),
            event_store=event_store,
        )

        command = use_case.execute(
            candidate=make_candidate(),
            mode=AttentionMode.BALANCED,
            recent_category_count=0,
            correlation_id="corr_1",
            trace_id="trace_1",
        )

        self.assertIsNotNone(command)
        self.assertEqual(command.command_type, LensCommandType.SHOW_ALERT)
        self.assertEqual(command.to_dict()["metadata"]["candidate_id"], "candidate_1")
        self.assertEqual(
            [event.event_type for event in event_store.events],
            [EventType.ALERT_CANDIDATE_CREATED, EventType.ALERT_SHOWN],
        )

    def test_suppresses_candidate_when_attention_policy_blocks_display(self) -> None:
        event_store = InMemoryEventStore()
        use_case = EvaluateAlertCandidate(
            attention_policy=AttentionPolicy(),
            event_store=event_store,
        )

        command = use_case.execute(
            candidate=make_candidate(confidence=0.2),
            mode=AttentionMode.BALANCED,
            recent_category_count=0,
            correlation_id="corr_1",
            trace_id="trace_1",
        )

        self.assertIsNone(command)
        self.assertEqual(
            [event.event_type for event in event_store.events],
            [EventType.ALERT_CANDIDATE_CREATED, EventType.ALERT_SUPPRESSED],
        )
        self.assertEqual(
            event_store.events[-1].metadata["reason"],
            "low_confidence_requires_confirmation",
        )
