from __future__ import annotations

from new_era.domain.attention import AlertCandidate
from new_era.domain.observations import Observation


class ObservationInterpreter:
    def to_alert_candidate(self, observation: Observation) -> AlertCandidate | None:
        raise NotImplementedError

    def interpret(self, observation: Observation) -> AlertCandidate | None:
        return self.to_alert_candidate(observation)

    def execute(self, observation: Observation) -> AlertCandidate | None:
        return self.to_alert_candidate(observation)

    def __call__(self, observation: Observation) -> AlertCandidate | None:
        return self.to_alert_candidate(observation)

    def convert(self, observation: Observation) -> AlertCandidate | None:
        return self.to_alert_candidate(observation)

    def resolve(self, observation: Observation) -> AlertCandidate | None:
        raise NotImplementedError
