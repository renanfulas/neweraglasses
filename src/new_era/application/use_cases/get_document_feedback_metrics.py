from __future__ import annotations

from dataclasses import dataclass

from new_era.application.ports import DocumentAnalysisStore, EventStore
from new_era.application.use_cases.record_document_analysis_feedback import (
    DocumentAnalysisFeedbackValue,
)
from new_era.domain.documents import ContractFindingType, DocumentAnalysisRecord
from new_era.domain.events import EventType
from new_era.domain.metrics import FeedbackAggregate, FindingTypeFeedbackAggregate


@dataclass(frozen=True, slots=True)
class DocumentFeedbackMetricsReadModel:
    user_id: str
    session_id: str
    aggregate: FeedbackAggregate
    by_finding_type: tuple[FindingTypeFeedbackAggregate, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "aggregate": self.aggregate.to_dict(),
            "by_finding_type": [metric.to_dict() for metric in self.by_finding_type],
        }


@dataclass(frozen=True, slots=True)
class GetDocumentFeedbackMetrics:
    analysis_store: DocumentAnalysisStore
    event_store: EventStore

    def execute(
        self,
        *,
        user_id: str,
        session_id: str,
    ) -> DocumentFeedbackMetricsReadModel:
        owned_records = tuple(
            record
            for record in self.analysis_store.list_by_session(session_id=session_id)
            if record.user_id == user_id
        )
        feedback_by_analysis_id = self._feedback_by_analysis_id(
            user_id=user_id,
            session_id=session_id,
            records=owned_records,
        )
        aggregate = self._build_aggregate(owned_records, feedback_by_analysis_id)
        by_finding_type = tuple(
            self._build_finding_metric(
                finding_type=finding_type,
                records=owned_records,
                feedback_by_analysis_id=feedback_by_analysis_id,
            )
            for finding_type in ContractFindingType
        )
        return DocumentFeedbackMetricsReadModel(
            user_id=user_id,
            session_id=session_id,
            aggregate=aggregate,
            by_finding_type=by_finding_type,
        )

    def _feedback_by_analysis_id(
        self,
        *,
        user_id: str,
        session_id: str,
        records: tuple[DocumentAnalysisRecord, ...],
    ) -> dict[str, DocumentAnalysisFeedbackValue]:
        analysis_ids = {record.analysis_id for record in records}
        if not analysis_ids:
            return {}

        latest_feedback: dict[str, DocumentAnalysisFeedbackValue] = {}
        feedback_events = self.event_store.list_events(
            user_id=user_id,
            session_id=session_id,
            module="documents",
            event_types={EventType.DOCUMENT_ANALYSIS_FEEDBACK_GIVEN},
        )
        for event in feedback_events:
            analysis_id = event.metadata.get("analysis_id")
            feedback_value = event.metadata.get("feedback")
            if not isinstance(analysis_id, str) or analysis_id not in analysis_ids:
                continue
            if not isinstance(feedback_value, str):
                continue
            try:
                latest_feedback[analysis_id] = DocumentAnalysisFeedbackValue(feedback_value)
            except ValueError:
                continue
        return latest_feedback

    def _build_aggregate(
        self,
        records: tuple[DocumentAnalysisRecord, ...],
        feedback_by_analysis_id: dict[str, DocumentAnalysisFeedbackValue],
    ) -> FeedbackAggregate:
        useful_feedback_count = sum(
            1
            for feedback in feedback_by_analysis_id.values()
            if feedback == DocumentAnalysisFeedbackValue.USEFUL
        )
        not_useful_feedback_count = sum(
            1
            for feedback in feedback_by_analysis_id.values()
            if feedback == DocumentAnalysisFeedbackValue.NOT_USEFUL
        )
        return FeedbackAggregate(
            analysis_count=len(records),
            feedback_count=len(feedback_by_analysis_id),
            useful_feedback_count=useful_feedback_count,
            not_useful_feedback_count=not_useful_feedback_count,
        )

    def _build_finding_metric(
        self,
        *,
        finding_type: ContractFindingType,
        records: tuple[DocumentAnalysisRecord, ...],
        feedback_by_analysis_id: dict[str, DocumentAnalysisFeedbackValue],
    ) -> FindingTypeFeedbackAggregate:
        analysis_count = 0
        feedback_count = 0
        useful_feedback_count = 0
        not_useful_feedback_count = 0

        for record in records:
            finding_types = {finding.finding_type for finding in record.analysis.findings}
            if finding_type not in finding_types:
                continue

            analysis_count += 1
            feedback = feedback_by_analysis_id.get(record.analysis_id)
            if feedback is None:
                continue

            feedback_count += 1
            if feedback == DocumentAnalysisFeedbackValue.USEFUL:
                useful_feedback_count += 1
            else:
                not_useful_feedback_count += 1

        return FindingTypeFeedbackAggregate(
            finding_type=finding_type,
            analysis_count=analysis_count,
            feedback_count=feedback_count,
            useful_feedback_count=useful_feedback_count,
            not_useful_feedback_count=not_useful_feedback_count,
        )
