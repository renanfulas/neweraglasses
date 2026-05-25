import json
import shutil
import sqlite3
from pathlib import Path
from tempfile import mkdtemp
from unittest import TestCase

from new_era.domain.documents import (
    ContractReviewAnalysis,
    DocumentAnalysisRecord,
)
from new_era.infrastructure.documents import InMemoryDocumentAnalysisStore
from new_era.infrastructure.documents.sqlite_document_analysis_store import (
    SQLiteDocumentAnalysisStore,
)


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

    def test_sqlite_store_persists_sanitized_analysis_history(self) -> None:
        temp_dir = mkdtemp()
        try:
            database_path = Path(temp_dir) / "document-analysis.sqlite3"
            store = SQLiteDocumentAnalysisStore(database_path=database_path)
            record = DocumentAnalysisRecord(
                user_id="user_1",
                session_id="session_1",
                observation_id="obs_1",
                trace_id="trace_1",
                source_type="plain_text",
                analysis=ContractReviewAnalysis(
                    extracted_text="full raw contract text that must not persist",
                    source_confidence=0.92,
                    review_confidence=0.81,
                    summary_title="Contract clause needs attention",
                    summary_body="This clause deserves review before signing.",
                ),
            )

            store.save(record)
            persisted = store.get(record.analysis_id)

            self.assertIsNotNone(persisted)
            self.assertEqual(persisted.analysis.extracted_text, "")
            with sqlite3.connect(database_path) as connection:
                row = connection.execute(
                    "SELECT analysis_json FROM document_analyses WHERE analysis_id = ?",
                    (record.analysis_id,),
                ).fetchone()
            analysis_json = json.loads(row[0])
            self.assertNotIn("extracted_text", analysis_json)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
