from unittest import TestCase

from new_era.application.use_cases import GetSessionTrace
from new_era.domain.events import Event, EventType
from new_era.infrastructure.events import InMemoryEventStore


class GetSessionTraceTest(TestCase):
    def test_projects_session_trace_from_events(self) -> None:
        event_store = InMemoryEventStore()
        event_store.append(
            Event(
                event_type=EventType.OBSERVATION_CREATED,
                user_id="user_1",
                session_id="session_1",
                module="grocery",
                correlation_id="corr_1",
                trace_id="trace_1",
                metadata={"summary": "Missing eggs in grocery session"},
            )
        )
        event_store.append(
            Event(
                event_type=EventType.ALERT_SHOWN,
                user_id="user_1",
                session_id="session_1",
                module="grocery",
                correlation_id="corr_1",
                trace_id="trace_1",
                metadata={"reason": "within_attention_budget"},
            )
        )

        read_model = GetSessionTrace(event_store=event_store).execute(
            session_id="session_1",
            trace_id="trace_1",
        )

        self.assertEqual(read_model.event_count, 2)
        self.assertEqual(
            [entry.step for entry in read_model.session_trace],
            ["observation", "decision"],
        )
        self.assertEqual(read_model.session_trace[0].title, "Observation captured")

    def test_filters_out_other_sessions(self) -> None:
        event_store = InMemoryEventStore()
        event_store.append(
            Event(
                event_type=EventType.OBSERVATION_CREATED,
                user_id="user_1",
                session_id="session_1",
                module="grocery",
                correlation_id="corr_1",
                trace_id="trace_1",
                metadata={"summary": "Missing eggs in grocery session"},
            )
        )
        event_store.append(
            Event(
                event_type=EventType.OBSERVATION_CREATED,
                user_id="user_2",
                session_id="session_2",
                module="documents",
                correlation_id="corr_2",
                trace_id="trace_2",
                metadata={"summary": "Contract review requested"},
            )
        )

        read_model = GetSessionTrace(event_store=event_store).execute(session_id="session_1")

        self.assertEqual(read_model.event_count, 1)
        self.assertEqual(read_model.session_trace[0].detail, "Missing eggs in grocery session")
