from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Mapping
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class UserSession:
    user_id: str
    module: str
    title: str
    metadata: Mapping[str, object] = field(default_factory=dict)
    session_id: str = field(default_factory=lambda: f"session_{uuid4().hex}")
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.user_id:
            raise ValueError("user_id is required")
        if not self.session_id:
            raise ValueError("session_id is required")
        if not self.module:
            raise ValueError("module is required")
        if not self.title:
            raise ValueError("title is required")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "module": self.module,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": dict(self.metadata),
        }
