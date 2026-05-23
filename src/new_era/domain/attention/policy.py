from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from new_era.domain.attention.models import (
    AlertCandidate,
    AlertPriority,
    AttentionBudget,
    AttentionDecision,
    AttentionMode,
    AttentionOutcome,
)


DEFAULT_CATEGORY_LIMITS: dict[AttentionMode, dict[str, int]] = {
    AttentionMode.ESSENTIAL: {
        "critical_safety": 999,
        "documents": 2,
        "grocery": 2,
        "uv_health": 1,
        "tips": 0,
    },
    AttentionMode.BALANCED: {
        "critical_safety": 999,
        "documents": 3,
        "grocery": 5,
        "uv_health": 2,
        "tips": 2,
    },
    AttentionMode.PROACTIVE: {
        "critical_safety": 999,
        "documents": 4,
        "grocery": 8,
        "uv_health": 3,
        "tips": 5,
    },
}


@dataclass(frozen=True, slots=True)
class AttentionPolicy:
    policy_version: str = "attention_v1"
    category_limits: dict[AttentionMode, dict[str, int]] = field(
        default_factory=lambda: {
            mode: limits.copy() for mode, limits in DEFAULT_CATEGORY_LIMITS.items()
        }
    )

    def evaluate(
        self,
        candidate: AlertCandidate,
        mode: AttentionMode,
        recent_category_count: int,
    ) -> AttentionDecision:
        limit = self._limit_for(mode, candidate.category)
        remaining = max(limit - recent_category_count, 0)
        budget = AttentionBudget(
            mode=mode,
            category=candidate.category,
            remaining=remaining,
            limit=limit,
        )

        if candidate.priority == AlertPriority.CRITICAL:
            return self._decision(
                outcome=AttentionOutcome.SHOW_NOW,
                reason="critical_priority_bypasses_regular_budget",
                candidate=candidate,
                budget=budget,
            )

        if candidate.confidence < 0.45:
            return self._decision(
                outcome=AttentionOutcome.REQUEST_CONFIRMATION,
                reason="low_confidence_requires_confirmation",
                candidate=candidate,
                budget=budget,
            )

        if limit <= 0:
            return self._decision(
                outcome=AttentionOutcome.SILENCE,
                reason="category_disabled_for_attention_mode",
                candidate=candidate,
                budget=budget,
            )

        if recent_category_count >= limit:
            return self._decision(
                outcome=AttentionOutcome.GROUP,
                reason="attention_budget_exceeded",
                candidate=candidate,
                budget=budget,
            )

        return self._decision(
            outcome=AttentionOutcome.SHOW_NOW,
            reason="within_attention_budget",
            candidate=candidate,
            budget=budget,
        )

    def _limit_for(self, mode: AttentionMode, category: str) -> int:
        mode_limits = self.category_limits.get(mode, {})
        return mode_limits.get(category, mode_limits.get("tips", 0))

    def _decision(
        self,
        outcome: AttentionOutcome,
        reason: str,
        candidate: AlertCandidate,
        budget: AttentionBudget,
    ) -> AttentionDecision:
        return AttentionDecision(
            decision_id=f"decision_{uuid4().hex}",
            decision_version=1,
            outcome=outcome,
            reason=reason,
            priority=candidate.priority,
            budget=budget,
        )
