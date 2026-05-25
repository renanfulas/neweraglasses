from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from new_era.domain.events import Event, EventType
from new_era.domain.sessions import UserSession
from new_era.infrastructure.events import SQLiteEventStore
from new_era.infrastructure.sessions import SQLiteSessionStore


class SQLiteStorageTest(TestCase):
    def test_event_store_persists_events_across_instances(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "new_era.sqlite3"
            first_store = SQLiteEventStore(database_path)
            first_store.append(
                Event(
                    event_type=EventType.OBSERVATION_CREATED,
                    user_id="user_1",
                    session_id="session_1",
                    module="grocery",
                    correlation_id="corr_1",
                    trace_id="trace_1",
                    metadata={"summary": "Missing eggs"},
                )
            )

            second_store = SQLiteEventStore(database_path)
            events = second_store.list_events(
                user_id="user_1",
                session_id="session_1",
                module="grocery",
            )

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].metadata["summary"], "Missing eggs")

    def test_session_store_persists_user_sessions_across_instances(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "new_era.sqlite3"
            first_store = SQLiteSessionStore(database_path)
            first_store.save(
                UserSession(
                    user_id="user_1",
                    session_id="session_1",
                    module="documents",
                    title="Contract review",
                )
            )

            second_store = SQLiteSessionStore(database_path)
            sessions = second_store.list_by_user(user_id="user_1", module="documents")

            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].session_id, "session_1")
