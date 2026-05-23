from unittest import TestCase

from new_era.application.services import DocumentSessionService
from new_era.domain.attention import AttentionMode
from new_era.domain.events import EventType


class DocumentSessionServiceTest(TestCase):
    def test_processes_contract_risk_to_delivered_alert(self) -> None:
        service = DocumentSessionService.build_default_simulation()

        result = service.process_contract_review(
            observation_id="obs_doc_1",
            user_id="user_1",
            session_id="session_1",
            document_text=(
                "Plano com fidelidade de 12 meses, renovacao automatica "
                "e multa de cancelamento."
            ),
            confidence=0.92,
            mode=AttentionMode.BALANCED,
            recent_category_count=0,
            correlation_id="corr_1",
            trace_id="trace_1",
        )

        self.assertTrue(result.candidate_created)
        self.assertEqual(result.outcome.value, "delivered")
        self.assertEqual(len(service.device_gateway.delivered_commands), 1)
        self.assertEqual(
            [event.event_type for event in service.event_store.events],
            [
                EventType.OBSERVATION_CREATED,
                EventType.ALERT_CANDIDATE_CREATED,
                EventType.ALERT_SHOWN,
                EventType.LENS_COMMAND_DELIVERED,
            ],
        )

    def test_returns_suppressed_without_candidate_when_no_risk_is_detected(self) -> None:
        service = DocumentSessionService.build_default_simulation()

        result = service.process_contract_review(
            observation_id="obs_doc_2",
            user_id="user_1",
            session_id="session_1",
            document_text="Horario de atendimento de segunda a sexta, sem clausulas adicionais.",
            confidence=0.92,
            mode=AttentionMode.BALANCED,
            recent_category_count=0,
            correlation_id="corr_1",
            trace_id="trace_1",
        )

        self.assertFalse(result.candidate_created)
        self.assertEqual(result.outcome.value, "suppressed")
        self.assertEqual(service.device_gateway.delivered_commands, [])
        self.assertEqual(
            [event.event_type for event in service.event_store.events],
            [EventType.OBSERVATION_CREATED],
        )
