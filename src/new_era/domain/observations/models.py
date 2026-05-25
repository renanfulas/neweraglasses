from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class ObservationKind(StrEnum):
    GROCERY_MISSING_ITEM = "grocery_missing_item"
    DOCUMENT_CONTRACT_REVIEW = "document_contract_review"


@dataclass(frozen=True, slots=True)
class Observation:
    observation_id: str
    user_id: str
    session_id: str
    module: str
    kind: ObservationKind
    summary: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
