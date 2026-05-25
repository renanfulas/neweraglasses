from unittest import TestCase

from new_era.domain.attention import (
    AlertCandidate,
    AlertPriority,
    AttentionMode,
    AttentionOutcome,
    AttentionPolicy,
)


def make_candidate(
    *,
    priority: AlertPriority = AlertPriority.MEDIUM,
    confidence: float = 0.9,
    category: str = "grocery",
) -> AlertCandidate:
    return AlertCandidate(
        candidate_id="candidate_1",
        user_id="user_1",
        session_id="session_1",
        module="grocery",
        alert_type="missing_item",
        title="Missing item",
        body="You still need eggs.",
        priority=priority,
        confidence=confidence,
        category=category,
    )


class AttentionPolicyTest(TestCase):
    def test_shows_candidate_inside_balanced_budget(self) -> None:
        policy = AttentionPolicy()

        decision = policy.evaluate(
            candidate=make_candidate(),
            mode=AttentionMode.BALANCED,
            recent_category_count=0,
        )

        self.assertEqual(decision.outcome, AttentionOutcome.SHOW_NOW)
        self.assertEqual(decision.reason, "within_attention_budget")
        self.assertTrue(decision.allows_display)

    def test_groups_candidate_when_budget_is_exceeded(self) -> None:
        policy = AttentionPolicy()

        decision = policy.evaluate(
            candidate=make_candidate(),
            mode=AttentionMode.BALANCED,
            recent_category_count=5,
        )

        self.assertEqual(decision.outcome, AttentionOutcome.GROUP)
        self.assertEqual(decision.reason, "attention_budget_exceeded")
        self.assertFalse(decision.allows_display)

    def test_low_confidence_requires_confirmation(self) -> None:
        policy = AttentionPolicy()

        decision = policy.evaluate(
            candidate=make_candidate(confidence=0.2),
            mode=AttentionMode.BALANCED,
            recent_category_count=0,
        )

        self.assertEqual(decision.outcome, AttentionOutcome.REQUEST_CONFIRMATION)
        self.assertEqual(decision.reason, "low_confidence_requires_confirmation")

    def test_critical_priority_bypasses_regular_budget(self) -> None:
        policy = AttentionPolicy()

        decision = policy.evaluate(
            candidate=make_candidate(
                priority=AlertPriority.CRITICAL,
                category="critical_safety",
            ),
            mode=AttentionMode.ESSENTIAL,
            recent_category_count=999,
        )

        self.assertEqual(decision.outcome, AttentionOutcome.SHOW_NOW)
        self.assertEqual(decision.reason, "critical_priority_bypasses_regular_budget")
