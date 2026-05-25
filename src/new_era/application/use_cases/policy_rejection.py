from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from new_era.domain.events.redaction import validate_event_metadata


@dataclass(frozen=True, slots=True)
class PolicyRejection:
    code: str
    message: str
    reason: str
    scope: str
    limit: int | None = None
    current: int | None = None
    retryable: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("code is required")
        if not self.message:
            raise ValueError("message is required")
        if not self.reason:
            raise ValueError("reason is required")
        if not self.scope:
            raise ValueError("scope is required")
        validate_event_metadata(self.metadata)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "code": self.code,
            "message": self.message,
            "reason": self.reason,
            "scope": self.scope,
            "retryable": self.retryable,
        }
        if self.limit is not None:
            payload["limit"] = self.limit
        if self.current is not None:
            payload["current"] = self.current
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


class PolicyRejectedError(Exception):
    def __init__(self, rejection: PolicyRejection) -> None:
        super().__init__(rejection.code)
        self.rejection = rejection
