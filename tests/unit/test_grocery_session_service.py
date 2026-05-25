from unittest import TestCase

from new_era.application.services import GrocerySessionService
from new_era.domain.attention import AttentionMode
from new_era.domain.events import EventType


class GrocerySessionServiceTest(TestCase):
    def test_processes_missing_item_to_delivered_alert(self) -> None:
        service = GrocerySessionService.build_default_simulation()

        result = service.process_missing_item(
            observation_id="obs_1",
            user_id="user_1",
            session_id="session_1",
            item_name="eggs",
            confidence=0.88,
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

    def test_suppresses_low_confidence_observation_before_delivery(self) -> None:
        service = GrocerySessionService.build_default_simulation()

        result = service.process_missing_item(
            observation_id="obs_2",
            user_id="user_1",
            session_id="session_1",
            item_name="eggs",
            confidence=0.2,
            mode=AttentionMode.BALANCED,
            recent_category_count=0,
            correlation_id="corr_1",
            trace_id="trace_1",
        )

        self.assertTrue(result.candidate_created)
        self.assertEqual(result.outcome.value, "suppressed")
        self.assertEqual(service.device_gateway.delivered_commands, [])
        self.assertEqual(service.event_store.events[-1].event_type, EventType.ALERT_SUPPRESSED)
