from unittest import TestCase

from fastapi.testclient import TestClient

from new_era.infrastructure.http.app import create_app


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
        client = TestClient(create_app())

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
        client = TestClient(create_app())

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
        client = TestClient(create_app())

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
        client = TestClient(create_app())

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

    def test_session_trace_endpoint_reads_persisted_trace_for_same_app_runtime(self) -> None:
        app = create_app()
        client = TestClient(app)

        client.post(
            "/api/simulations/grocery/missing-item",
            json={
                "user_id": "user_1",
                "session_id": "session_trace",
                "item_name": "eggs",
                "confidence": 0.88,
                "mode": "balanced",
                "recent_category_count": 0,
                "observation_id": "obs_trace_1",
                "correlation_id": "corr_trace_1",
                "trace_id": "trace_shared_1",
            },
        )

        response = client.get("/api/sessions/session_trace/trace?trace_id=trace_shared_1")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["session_id"], "session_trace")
        self.assertEqual(payload["event_count"], 4)
        self.assertEqual(
            [entry["event_type"] for entry in payload["session_trace"]],
            [
                "observation_created",
                "alert_candidate_created",
                "alert_shown",
                "lens_command_delivered",
            ],
        )

    def test_document_analysis_job_endpoints_support_idempotent_enqueue_and_status(self) -> None:
        app = create_app()
        client = TestClient(app)

        first_response = client.post(
            "/api/jobs/documents/contract-analysis",
            json={
                "user_id": "user_1",
                "session_id": "session_jobs",
                "artifact_label": "gym-contract.pdf",
                "source_type": "pwa_upload",
                "idempotency_key": "idem_contract_123",
                "correlation_id": "corr_jobs_1",
                "trace_id": "trace_jobs_1",
            },
        )
        second_response = client.post(
            "/api/jobs/documents/contract-analysis",
            json={
                "user_id": "user_1",
                "session_id": "session_jobs",
                "artifact_label": "gym-contract.pdf",
                "source_type": "pwa_upload",
                "idempotency_key": "idem_contract_123",
                "correlation_id": "corr_jobs_2",
                "trace_id": "trace_jobs_2",
            },
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        first_payload = first_response.json()
        second_payload = second_response.json()
        self.assertEqual(first_payload["job_id"], second_payload["job_id"])
        self.assertEqual(first_payload["status"], "queued")

        status_response = client.get(f"/api/jobs/{first_payload['job_id']}")

        self.assertEqual(status_response.status_code, 200)
        status_payload = status_response.json()
        self.assertEqual(status_payload["job_id"], first_payload["job_id"])
        self.assertEqual(status_payload["metadata"]["artifact_label"], "gym-contract.pdf")

    def test_document_analysis_job_status_transition_endpoint_updates_state(self) -> None:
        app = create_app()
        client = TestClient(app)

        enqueue_response = client.post(
            "/api/jobs/documents/contract-analysis",
            json={
                "user_id": "user_1",
                "session_id": "session_jobs",
                "artifact_label": "gym-contract.pdf",
                "source_type": "pwa_upload",
                "idempotency_key": "idem_contract_456",
                "correlation_id": "corr_jobs_1",
                "trace_id": "trace_jobs_1",
            },
        )
        job_id = enqueue_response.json()["job_id"]

        running_response = client.post(
            f"/api/jobs/{job_id}/status",
            json={
                "target_status": "running",
                "correlation_id": "corr_jobs_2",
                "trace_id": "trace_jobs_1",
            },
        )
        success_response = client.post(
            f"/api/jobs/{job_id}/status",
            json={
                "target_status": "succeeded",
                "correlation_id": "corr_jobs_3",
                "trace_id": "trace_jobs_1",
            },
        )
        trace_response = client.get("/api/sessions/session_jobs/trace")

        self.assertEqual(running_response.status_code, 200)
        self.assertEqual(success_response.status_code, 200)
        self.assertEqual(running_response.json()["status"], "running")
        self.assertEqual(success_response.json()["status"], "succeeded")
        self.assertEqual(trace_response.status_code, 200)
        self.assertEqual(
            [entry["event_type"] for entry in trace_response.json()["session_trace"]],
            ["job_started", "job_status_updated", "job_completed"],
        )
