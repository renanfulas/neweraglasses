from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from new_era.application.ports import DocumentAnalysisStore, EventStore
from new_era.domain.events import Event, EventType


class DocumentAnalysisFeedbackValue(StrEnum):
    USEFUL = "useful"
    NOT_USEFUL = "not_useful"


@dataclass(frozen=True, slots=True)
class DocumentAnalysisFeedbackResult:
    event_id: str
    analysis_id: str
    feedback: DocumentAnalysisFeedbackValue


@dataclass(frozen=True, slots=True)
class RecordDocumentAnalysisFeedback:
    analysis_store: DocumentAnalysisStore
    event_store: EventStore

    def execute(
        self,
        *,
        analysis_id: str,
        user_id: str,
        session_id: str,
        feedback: DocumentAnalysisFeedbackValue,
        correlation_id: str,
        trace_id: str | None = None,
    ) -> DocumentAnalysisFeedbackResult | None:
        record = self.analysis_store.get(analysis_id)
        if record is None or record.user_id != user_id or record.session_id != session_id:
            return None

        feedback_event = Event(
            event_type=EventType.DOCUMENT_ANALYSIS_FEEDBACK_GIVEN,
            user_id=user_id,
            session_id=session_id,
            module="documents",
            correlation_id=correlation_id,
            trace_id=trace_id or record.trace_id,
            metadata={
                "analysis_id": analysis_id,
                "feedback": feedback.value,
                "source": "pwa_companion",
            },
        )
        self.event_store.append(feedback_event)
        return DocumentAnalysisFeedbackResult(
            event_id=feedback_event.event_id,
            analysis_id=analysis_id,
            feedback=feedback,
        )


@dataclass(frozen=True, slots=True)
class GetDocumentAnalysisFeedback:
    event_store: EventStore

    def execute(
        self,
        *,
        analysis_id: str,
        user_id: str,
        session_id: str,
    ) -> DocumentAnalysisFeedbackValue | None:
        latest_feedback: DocumentAnalysisFeedbackValue | None = None
        for event in self.event_store.list_events(session_id=session_id, user_id=user_id):
            if event.event_type != EventType.DOCUMENT_ANALYSIS_FEEDBACK_GIVEN:
                continue
            if event.metadata.get("analysis_id") != analysis_id:
                continue
            feedback_value = event.metadata.get("feedback")
            if isinstance(feedback_value, str):
                latest_feedback = DocumentAnalysisFeedbackValue(feedback_value)
        return latest_feedback
