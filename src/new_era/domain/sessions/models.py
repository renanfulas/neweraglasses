from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class UserSession:
    user_id: str
    session_id: str
    module: str
    title: str
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "module": self.module,
            "title": self.title,
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
