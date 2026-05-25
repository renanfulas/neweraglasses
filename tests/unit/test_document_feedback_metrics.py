from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from new_era.application.use_cases.get_document_feedback_metrics import (
    GetDocumentFeedbackMetrics,
)
from new_era.domain.documents import (
    ContractFinding,
    ContractFindingType,
    ContractReviewAnalysis,
    DocumentAnalysisRecord,
)
from new_era.domain.events import Event, EventType
from new_era.infrastructure.documents import (
    InMemoryDocumentAnalysisStore,
    SQLiteDocumentAnalysisStore,
)
from new_era.infrastructure.events import InMemoryEventStore, SQLiteEventStore


def build_analysis(
    *,
    findings: tuple[ContractFinding, ...] = (),
) -> ContractReviewAnalysis:
    return ContractReviewAnalysis(
        extracted_text="Contrato de servico",
        source_confidence=0.91,
        review_confidence=0.82,
        summary_title="Contract clause needs attention",
        summary_body="Review before signing.",
        findings=findings,
    )


def build_record(
    *,
    analysis_id: str,
    user_id: str,
    session_id: str,
    trace_id: str,
    findings: tuple[ContractFinding, ...] = (),
) -> DocumentAnalysisRecord:
    return DocumentAnalysisRecord(
        analysis_id=analysis_id,
        user_id=user_id,
        session_id=session_id,
        observation_id=f"obs_{analysis_id}",
        trace_id=trace_id,
        source_type="pwa_upload",
        analysis=build_analysis(findings=findings),
    )


def build_feedback_event(
    *,
    event_id: str,
    user_id: str,
    session_id: str,
    trace_id: str,
    analysis_id: str,
    feedback: str,
) -> Event:
    return Event(
        event_id=event_id,
        event_type=EventType.DOCUMENT_ANALYSIS_FEEDBACK_GIVEN,
        user_id=user_id,
        session_id=session_id,
        module="documents",
        correlation_id=f"corr_{event_id}",
        trace_id=trace_id,
        metadata={
            "analysis_id": analysis_id,
            "feedback": feedback,
            "source": "pwa_companion",
        },
    )


class GetDocumentFeedbackMetricsTest(TestCase):
    def test_aggregates_owned_feedback_metrics_by_session_and_finding_type(self) -> None:
        analysis_store = InMemoryDocumentAnalysisStore()
        event_store = InMemoryEventStore()

        first_record = build_record(
            analysis_id="analysis_1",
            user_id="user_1",
            session_id="session_1",
            trace_id="trace_1",
            findings=(
                ContractFinding(
                    finding_type=ContractFindingType.AUTOMATIC_RENEWAL,
                    label="automatic renewal",
                    excerpt="renovacao automatica",
                    confidence=0.94,
                ),
                ContractFinding(
                    finding_type=ContractFindingType.CANCELLATION_FEE,
                    label="cancellation fee",
                    excerpt="multa de cancelamento",
                    confidence=0.89,
                ),
            ),
        )
        second_record = build_record(
            analysis_id="analysis_2",
            user_id="user_1",
            session_id="session_1",
            trace_id="trace_2",
            findings=(
                ContractFinding(
                    finding_type=ContractFindingType.MINIMUM_COMMITMENT,
                    label="minimum commitment",
                    excerpt="prazo minimo",
                    confidence=0.84,
                ),
            ),
        )
        third_record = build_record(
            analysis_id="analysis_3",
            user_id="user_1",
            session_id="session_1",
            trace_id="trace_3",
        )
        foreign_record = build_record(
            analysis_id="analysis_4",
            user_id="user_2",
            session_id="session_1",
            trace_id="trace_4",
            findings=(
                ContractFinding(
                    finding_type=ContractFindingType.FEES_OR_INTEREST,
                    label="fees or interest",
                    excerpt="juros",
                    confidence=0.79,
                ),
            ),
        )

        for record in (first_record, second_record, third_record, foreign_record):
            analysis_store.save(record)

        event_store.append(
            build_feedback_event(
                event_id="evt_1",
                user_id="user_1",
                session_id="session_1",
                trace_id="trace_1",
                analysis_id="analysis_1",
                feedback="useful",
            )
        )
        event_store.append(
            build_feedback_event(
                event_id="evt_2",
                user_id="user_1",
                session_id="session_1",
                trace_id="trace_1",
                analysis_id="analysis_1",
                feedback="not_useful",
            )
        )
        event_store.append(
            build_feedback_event(
                event_id="evt_3",
                user_id="user_1",
                session_id="session_1",
                trace_id="trace_3",
                analysis_id="analysis_3",
                feedback="useful",
            )
        )
        event_store.append(
            build_feedback_event(
                event_id="evt_4",
                user_id="user_2",
                session_id="session_1",
                trace_id="trace_4",
                analysis_id="analysis_4",
                feedback="useful",
            )
        )
        event_store.append(
            build_feedback_event(
                event_id="evt_5",
                user_id="user_1",
                session_id="session_1",
                trace_id="trace_5",
                analysis_id="analysis_missing",
                feedback="useful",
            )
        )

        read_model = GetDocumentFeedbackMetrics(
            analysis_store=analysis_store,
            event_store=event_store,
        ).execute(user_id="user_1", session_id="session_1")

        self.assertEqual(read_model.aggregate.analysis_count, 3)
        self.assertEqual(read_model.aggregate.feedback_count, 2)
        self.assertEqual(read_model.aggregate.useful_feedback_count, 1)
        self.assertEqual(read_model.aggregate.not_useful_feedback_count, 1)
        self.assertEqual(read_model.aggregate.feedback_rate, 0.67)
        self.assertEqual(read_model.aggregate.useful_feedback_rate, 0.5)

        metrics_by_type = {
            metric.finding_type: metric
            for metric in read_model.by_finding_type
        }
        self.assertEqual(
            metrics_by_type[ContractFindingType.AUTOMATIC_RENEWAL].not_useful_feedback_count,
            1,
        )
        self.assertEqual(
            metrics_by_type[ContractFindingType.CANCELLATION_FEE].feedback_count,
            1,
        )
        self.assertEqual(
            metrics_by_type[ContractFindingType.MINIMUM_COMMITMENT].analysis_count,
            1,
        )
        self.assertEqual(
            metrics_by_type[ContractFindingType.MINIMUM_COMMITMENT].feedback_count,
            0,
        )
        self.assertEqual(
            metrics_by_type[ContractFindingType.FEES_OR_INTEREST].analysis_count,
            0,
        )

    def test_returns_empty_metrics_when_session_has_no_owned_analyses(self) -> None:
        analysis_store = InMemoryDocumentAnalysisStore()
        event_store = InMemoryEventStore()
        analysis_store.save(
            build_record(
                analysis_id="analysis_foreign",
                user_id="user_2",
                session_id="session_1",
                trace_id="trace_foreign",
            )
        )
        event_store.append(
            build_feedback_event(
                event_id="evt_foreign",
                user_id="user_2",
                session_id="session_1",
                trace_id="trace_foreign",
                analysis_id="analysis_foreign",
                feedback="useful",
            )
        )

        read_model = GetDocumentFeedbackMetrics(
            analysis_store=analysis_store,
            event_store=event_store,
        ).execute(user_id="user_1", session_id="session_1")

        self.assertEqual(read_model.aggregate.analysis_count, 0)
        self.assertEqual(read_model.aggregate.feedback_count, 0)
        self.assertTrue(
            all(metric.analysis_count == 0 for metric in read_model.by_finding_type)
        )

    def test_reads_feedback_metrics_from_sqlite_backed_stores(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "new_era.sqlite3"
            analysis_store = SQLiteDocumentAnalysisStore(database_path)
            event_store = SQLiteEventStore(database_path)
            analysis_store.save(
                build_record(
                    analysis_id="analysis_sqlite",
                    user_id="user_1",
                    session_id="session_1",
                    trace_id="trace_sqlite",
                    findings=(
                        ContractFinding(
                            finding_type=ContractFindingType.FEES_OR_INTEREST,
                            label="fees or interest",
                            excerpt="juros",
                            confidence=0.87,
                        ),
                    ),
                )
            )
            event_store.append(
                build_feedback_event(
                    event_id="evt_sqlite",
                    user_id="user_1",
                    session_id="session_1",
                    trace_id="trace_sqlite",
                    analysis_id="analysis_sqlite",
                    feedback="useful",
                )
            )

            read_model = GetDocumentFeedbackMetrics(
                analysis_store=analysis_store,
                event_store=event_store,
            ).execute(user_id="user_1", session_id="session_1")

        self.assertEqual(read_model.aggregate.analysis_count, 1)
        self.assertEqual(read_model.aggregate.feedback_count, 1)
        self.assertEqual(
            {
                metric.finding_type: metric.feedback_count
                for metric in read_model.by_finding_type
            }[ContractFindingType.FEES_OR_INTEREST],
            1,
        )
