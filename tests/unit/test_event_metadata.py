from unittest import TestCase

from new_era.domain.events import Event, EventType, ForbiddenMetadataError


class EventMetadataTest(TestCase):
    def test_rejects_raw_sensitive_metadata(self) -> None:
        with self.assertRaises(ForbiddenMetadataError):
            Event(
                event_type=EventType.ALERT_SHOWN,
                user_id="user_1",
                session_id="session_1",
                module="documents",
                correlation_id="corr_1",
                trace_id="trace_1",
                metadata={"raw_document_text": "secret clause"},
            )

    def test_accepts_structured_redacted_metadata(self) -> None:
        event = Event(
            event_type=EventType.ALERT_SHOWN,
            user_id="user_1",
            session_id="session_1",
            module="documents",
            correlation_id="corr_1",
            trace_id="trace_1",
            metadata={"excerpt_id": "excerpt_1", "confidence_bucket": "high"},
        )

        self.assertEqual(event.to_dict()["metadata"]["excerpt_id"], "excerpt_1")
