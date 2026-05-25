from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class AttentionMode(StrEnum):
    ESSENTIAL = "essential"
    BALANCED = "balanced"
    PROACTIVE = "proactive"


class AlertPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AttentionOutcome(StrEnum):
    SHOW_NOW = "show_now"
    GROUP = "group"
    DELAY = "delay"
    SILENCE = "silence"
    REQUEST_CONFIRMATION = "request_confirmation"


@dataclass(frozen=True, slots=True)
class AlertCandidate:
    candidate_id: str
    user_id: str
    session_id: str
    module: str
    alert_type: str
    title: str
    body: str
    priority: AlertPriority
    confidence: float
    category: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AttentionBudget:
    mode: AttentionMode
    category: str
    remaining: int
    limit: int


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
