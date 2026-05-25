from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4


class AttentionMode(StrEnum):
    ESSENTIAL = "essential"
    BALANCED = "balanced"
    PROACTIVE = "proactive"


class AlertPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class AlertCandidate:
    user_id: str
    session_id: str
    module: str
    alert_type: str
    category: str
    priority: AlertPriority
    confidence: float
    title: str
    body: str
    candidate_id: str = field(default_factory=lambda: f"candidate_{uuid4().hex}")


@dataclass(frozen=True, slots=True)
class AttentionBudget:
    mode: AttentionMode
    category: str
    remaining: int
    limit: int


class AttentionOutcome(StrEnum):
    SHOW_NOW = "show_now"
    REQUEST_CONFIRMATION = "request_confirmation"
    SILENCE = "silence"
    GROUP = "group"


@dataclass(frozen=True, slots=True)
class AttentionDecision:
    decision_id: str
    decision_version: int
    outcome: AttentionOutcome
    reason: str
    priority: AlertPriority
    budget: AttentionBudget

    @property
    def allows_display(self) -> bool:
        return self.outcome == AttentionOutcome.SHOW_NOW
