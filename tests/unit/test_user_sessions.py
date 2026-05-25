from unittest import TestCase

from new_era.application.use_cases import (
    ListUserSessions,
    SessionOwnershipError,
    StartUserSession,
)
from new_era.infrastructure.sessions import InMemorySessionStore


class UserSessionsTest(TestCase):
    def test_starts_and_lists_sessions_for_user(self) -> None:
        session_store = InMemorySessionStore()
        starter = StartUserSession(session_store=session_store)

        session = starter.execute(user_id="user_1", module="grocery")
        page = ListUserSessions(session_store=session_store).execute(user_id="user_1")

        self.assertEqual(session.user_id, "user_1")
        self.assertEqual(session.module, "grocery")
        self.assertEqual(page.session_count, 1)
        self.assertEqual(page.sessions[0].session_id, session.session_id)

    def test_rejects_reusing_session_for_another_user(self) -> None:
        session_store = InMemorySessionStore()
        starter = StartUserSession(session_store=session_store)
        session = starter.execute(
            user_id="user_1",
            module="documents",
            session_id="session_owned",
        )

        with self.assertRaises(SessionOwnershipError):
            starter.execute(
                user_id="user_2",
                module="documents",
                session_id=session.session_id,
            )

    def test_paginates_user_sessions(self) -> None:
        session_store = InMemorySessionStore()
        starter = StartUserSession(session_store=session_store)
        starter.execute(user_id="user_1", module="grocery", session_id="session_1")
        starter.execute(user_id="user_1", module="documents", session_id="session_2")

        lister = ListUserSessions(session_store=session_store)
        first_page = lister.execute(user_id="user_1", limit=1)
        second_page = lister.execute(
            user_id="user_1",
            limit=1,
            cursor=first_page.next_cursor,
        )

        self.assertEqual(first_page.session_count, 1)
        self.assertIsNotNone(first_page.next_cursor)
        self.assertEqual(second_page.session_count, 1)
        self.assertIsNone(second_page.next_cursor)
