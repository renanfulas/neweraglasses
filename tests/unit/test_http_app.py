from unittest import TestCase

from fastapi.testclient import TestClient

from new_era.application.services import DocumentSessionService, GrocerySessionService
from new_era.infrastructure.http.app import (
    create_app,
    get_document_session_service,
    get_grocery_session_service,
)


class HttpAppTest(TestCase):
    def test_root_serves_pwa_shell(self) -> None:
        client = TestClient(create_app())

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Context, attention, and display in one loop.", response.text)
        self.assertIn("Contracts", response.text)

    def test_health_endpoint_returns_ok(self) -> None:
        client = TestClient(create_app())

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_manifest_endpoint_is_available(self) -> None:
        client = TestClient(create_app())

        response = client.get("/manifest.webmanifest")

        self.assertEqual(response.status_code, 200)
        self.assertIn('"name": "New Era Simulator"', response.text)

    def test_grocery_simulation_endpoint_processes_missing_item(self) -> None:
        app = create_app()
        service = GrocerySessionService.build_default_simulation()
        app.dependency_overrides[get_grocery_session_service] = lambda: service
        client = TestClient(app)

        response = client.post(
            "/api/simulations/grocery/missing-item",
            json={
                "user_id": "user_1",
                "session_id": "session_1",
                "item_name": "eggs",
                "confidence": 0.88,
                "mode": "balanced",
                "recent_category_count": 0,
                "observation_id": "obs_1",
                "correlation_id": "corr_1",
                "trace_id": "trace_1",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["outcome"], "delivered")
        self.assertTrue(payload["candidate_created"])
        self.assertEqual(payload["command"]["title"], "Missing eggs")
        self.assertEqual(payload["event_count"], 4)
        self.assertEqual(payload["delivered_commands_count"], 1)
        self.assertEqual(
            [entry["step"] for entry in payload["session_trace"]],
            ["observation", "candidate", "decision", "delivery"],
        )
        self.assertEqual(
            [entry["event_type"] for entry in payload["session_trace"]],
            [
                "observation_created",
                "alert_candidate_created",
                "alert_shown",
                "lens_command_delivered",
            ],
        )

    def test_grocery_simulation_endpoint_returns_suppressed_for_low_confidence(self) -> None:
        app = create_app()
        service = GrocerySessionService.build_default_simulation()
        app.dependency_overrides[get_grocery_session_service] = lambda: service
        client = TestClient(app)

        response = client.post(
            "/api/simulations/grocery/missing-item",
            json={
                "user_id": "user_1",
                "session_id": "session_1",
                "item_name": "eggs",
                "confidence": 0.2,
                "mode": "balanced",
                "recent_category_count": 0,
                "observation_id": "obs_2",
                "correlation_id": "corr_1",
                "trace_id": "trace_1",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["outcome"], "suppressed")
        self.assertTrue(payload["candidate_created"])
        self.assertIsNone(payload["command"])
        self.assertEqual(payload["delivered_commands_count"], 0)
        self.assertEqual(
            [entry["step"] for entry in payload["session_trace"]],
            ["observation", "candidate", "decision"],
        )
        self.assertEqual(
            [entry["event_type"] for entry in payload["session_trace"]],
            [
                "observation_created",
                "alert_candidate_created",
                "alert_suppressed",
            ],
        )

    def test_document_contract_review_endpoint_processes_risk_signal(self) -> None:
        app = create_app()
        service = DocumentSessionService.build_default_simulation()
        app.dependency_overrides[get_document_session_service] = lambda: service
        client = TestClient(app)

        response = client.post(
            "/api/simulations/documents/contract-review",
            json={
                "user_id": "user_1",
                "session_id": "session_1",
                "document_text": (
                    "Contrato com renovacao automatica, multa de cancelamento "
                    "e fidelidade de 12 meses."
                ),
                "confidence": 0.92,
                "mode": "balanced",
                "recent_category_count": 0,
                "observation_id": "obs_doc_1",
                "correlation_id": "corr_doc_1",
                "trace_id": "trace_doc_1",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["outcome"], "delivered")
        self.assertTrue(payload["candidate_created"])
        self.assertEqual(payload["command"]["title"], "Contract clause needs attention")
        self.assertEqual(
            [entry["step"] for entry in payload["session_trace"]],
            ["observation", "candidate", "decision", "delivery"],
        )

    def test_document_contract_review_endpoint_returns_observation_only_when_no_risk_is_found(self) -> None:
        app = create_app()
        service = DocumentSessionService.build_default_simulation()
        app.dependency_overrides[get_document_session_service] = lambda: service
        client = TestClient(app)

        response = client.post(
            "/api/simulations/documents/contract-review",
            json={
                "user_id": "user_1",
                "session_id": "session_1",
                "document_text": "Horario de atendimento de segunda a sexta.",
                "confidence": 0.92,
                "mode": "balanced",
                "recent_category_count": 0,
                "observation_id": "obs_doc_2",
                "correlation_id": "corr_doc_1",
                "trace_id": "trace_doc_1",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["outcome"], "suppressed")
        self.assertFalse(payload["candidate_created"])
        self.assertIsNone(payload["command"])
        self.assertEqual(
            [entry["event_type"] for entry in payload["session_trace"]],
            ["observation_created"],
        )
