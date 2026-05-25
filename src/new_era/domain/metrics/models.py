from __future__ import annotations

from dataclasses import dataclass

from new_era.domain.documents import ContractFindingType


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 2)


@dataclass(frozen=True, slots=True)
class FeedbackAggregate:
    analysis_count: int = 0
    feedback_count: int = 0
    useful_feedback_count: int = 0
    not_useful_feedback_count: int = 0

    @property
    def feedback_rate(self) -> float | None:
        return _ratio(self.feedback_count, self.analysis_count)

    @property
    def useful_feedback_rate(self) -> float | None:
        return _ratio(self.useful_feedback_count, self.feedback_count)

    def to_dict(self) -> dict[str, object]:
        return {
            "analysis_count": self.analysis_count,
            "feedback_count": self.feedback_count,
            "useful_feedback_count": self.useful_feedback_count,
            "not_useful_feedback_count": self.not_useful_feedback_count,
            "feedback_rate": self.feedback_rate,
            "useful_feedback_rate": self.useful_feedback_rate,
        }


@dataclass(frozen=True, slots=True)
class FindingTypeFeedbackAggregate(FeedbackAggregate):
    finding_type: ContractFindingType = ContractFindingType.AUTOMATIC_RENEWAL

    def to_dict(self) -> dict[str, object]:
        payload = FeedbackAggregate.to_dict(self)
        payload["finding_type"] = self.finding_type.value
        return payload
