from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory

from new_era.domain.events import Event, EventType
from new_era.domain.sessions import UserSession
from new_era.infrastructure.events import SQLiteEventStore
from new_era.infrastructure.sessions import SQLiteSessionStore


class SQLiteStorageTests(unittest.TestCase):
    def test_event_store_round_trips_records(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = f"{temp_dir}\\runtime.sqlite3"
            store = SQLiteEventStore(database_path)
            event = Event(
                event_type=EventType.OBSERVATION_CREATED,
                user_id="user_sqlite",
                session_id="session_sqlite",
                module="documents",
                correlation_id="corr_sqlite",
                trace_id="trace_sqlite",
                metadata={"summary": "Smoke event"},
            )

            store.append(event)
            events = store.list_events(session_id="session_sqlite")

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].event_id, event.event_id)
            self.assertEqual(events[0].metadata["summary"], "Smoke event")

    def test_session_store_round_trips_records(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = f"{temp_dir}\\runtime.sqlite3"
            store = SQLiteSessionStore(database_path)
            session = UserSession(
                user_id="user_sqlite",
                session_id="session_sqlite",
                module="documents",
                title="SQLite session",
                metadata={"origin": "smoke"},
            )

            store.save(session)
            restored = store.get("session_sqlite")
            listed = store.list_by_user("user_sqlite")

            self.assertIsNotNone(restored)
            self.assertEqual(restored.session_id, session.session_id)
            self.assertEqual(restored.metadata["origin"], "smoke")
            self.assertEqual(len(listed), 1)
