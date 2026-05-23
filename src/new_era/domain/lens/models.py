from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from new_era.domain.attention.models import AlertPriority


class LensCommandType(StrEnum):
    SHOW_ALERT = "show_alert"


@dataclass(frozen=True, slots=True)
class LensInteraction:
    can_dismiss: bool = True
    can_mark_useful: bool = True


@dataclass(frozen=True, slots=True)
class LensCommand:
    command_id: str
    command_version: int
    command_type: LensCommandType
    priority: AlertPriority
    title: str
    body: str
    duration_ms: int
    interaction: LensInteraction = field(default_factory=LensInteraction)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.duration_ms <= 0:
            raise ValueError("duration_ms must be positive")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, object]:
        return {
            "command_id": self.command_id,
            "command_version": self.command_version,
            "command_type": self.command_type.value,
            "priority": self.priority.value,
            "title": self.title,
            "body": self.body,
            "duration_ms": self.duration_ms,
            "interaction": {
                "can_dismiss": self.interaction.can_dismiss,
                "can_mark_useful": self.interaction.can_mark_useful,
            },
            "metadata": dict(self.metadata),
        }
