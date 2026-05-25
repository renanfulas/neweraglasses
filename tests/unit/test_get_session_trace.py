from __future__ import annotations

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
        self.assertEqual(
            read_model.session_trace[0].detail,
            "Missing eggs in grocery session",
        )

    def test_paginates_trace_with_cursor(self) -> None:
        event_store = InMemoryEventStore()
        for index, event_type in enumerate(
            (
                EventType.OBSERVATION_CREATED,
                EventType.ALERT_CANDIDATE_CREATED,
                EventType.ALERT_SHOWN,
            ),
            start=1,
        ):
            event_store.append(
                Event(
                    event_type=event_type,
                    user_id="user_1",
                    session_id="session_1",
                    module="grocery",
                    correlation_id="corr_1",
                    trace_id="trace_1",
                    metadata={"summary": f"event {index}"},
                )
            )

        reader = GetSessionTrace(event_store=event_store)
        first_page = reader.execute(session_id="session_1", limit=2)
        second_page = reader.execute(
            session_id="session_1",
            limit=2,
            cursor=first_page.next_cursor,
        )

        self.assertEqual(first_page.event_count, 2)
        self.assertIsNotNone(first_page.next_cursor)
        self.assertEqual(second_page.event_count, 1)
        self.assertIsNone(second_page.next_cursor)
        self.assertEqual(second_page.session_trace[0].event_type, "alert_shown")

    def test_filters_trace_by_user_module_event_type_and_step(self) -> None:
        event_store = InMemoryEventStore()
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
        event_store.append(
            Event(
                event_type=EventType.ALERT_SUPPRESSED,
                user_id="user_1",
                session_id="session_1",
                module="documents",
                correlation_id="corr_2",
                trace_id="trace_2",
                metadata={"reason": "low_confidence"},
            )
        )
        event_store.append(
            Event(
                event_type=EventType.ALERT_SHOWN,
                user_id="user_2",
                session_id="session_1",
                module="grocery",
                correlation_id="corr_3",
                trace_id="trace_3",
                metadata={"reason": "other_user"},
            )
        )

        read_model = GetSessionTrace(event_store=event_store).execute(
            user_id="user_1",
            session_id="session_1",
            module="grocery",
            event_types={EventType.ALERT_SHOWN},
            steps={"decision"},
        )

        self.assertEqual(read_model.event_count, 1)
        self.assertEqual(read_model.session_trace[0].detail, "within_attention_budget")
