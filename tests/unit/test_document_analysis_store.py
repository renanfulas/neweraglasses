from unittest import TestCase

from new_era.domain.documents import (
    ContractReviewAnalysis,
    DocumentAnalysisRecord,
)
from new_era.infrastructure.documents import InMemoryDocumentAnalysisStore


class InMemoryDocumentAnalysisStoreTest(TestCase):
    def test_saves_gets_and_lists_records_by_session(self) -> None:
        store = InMemoryDocumentAnalysisStore()
        analysis = ContractReviewAnalysis(
            extracted_text="sample text",
            source_confidence=0.92,
            review_confidence=0.81,
            summary_title="Contract clause needs attention",
            summary_body="This clause deserves review before signing.",
        )
        first_record = DocumentAnalysisRecord(
            user_id="user_1",
            session_id="session_1",
            observation_id="obs_1",
            trace_id="trace_1",
            source_type="plain_text",
            analysis=analysis,
        )
        second_record = DocumentAnalysisRecord(
            user_id="user_1",
            session_id="session_1",
            observation_id="obs_2",
            trace_id="trace_2",
            source_type="image_ocr",
            analysis=analysis,
        )

        store.save(first_record)
        store.save(second_record)

        self.assertEqual(store.get(first_record.analysis_id), first_record)
        session_records = store.list_by_session(session_id="session_1")
        self.assertEqual(len(session_records), 2)
        self.assertEqual(
            {record.analysis_id for record in session_records},
            {first_record.analysis_id, second_record.analysis_id},
        )
