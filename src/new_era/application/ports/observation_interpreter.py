from __future__ import annotations

from typing import Protocol

from new_era.domain.attention import AlertCandidate
from new_era.domain.observations import Observation


class ObservationInterpreter(Protocol):
    def to_alert_candidate(self, observation: Observation) -> AlertCandidate | None:
        raise NotImplementedError
