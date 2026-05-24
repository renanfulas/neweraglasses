import base64
import io
from unittest import TestCase

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

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
        self.assertIsNotNone(payload["analysis_id"])
        self.assertGreaterEqual(payload["analysis"]["review_confidence"], 0.6)
        self.assertIn("automatic_renewal", str(payload["analysis"]["findings"][0]["finding_type"]))
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

    def test_document_contract_review_endpoint_supports_image_ocr(self) -> None:
        client = TestClient(create_app())
        image = Image.new("RGB", (1200, 240), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=48)
        draw.text(
            (40, 80),
            "AUTOMATIC RENEWAL CANCELLATION FEE",
            fill="black",
            font=font,
        )
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")

        response = client.post(
            "/api/simulations/documents/contract-review",
            json={
                "user_id": "user_1",
                "session_id": "session_ocr_1",
                "document_image_base64": image_base64,
                "mode": "balanced",
                "recent_category_count": 0,
                "observation_id": "obs_doc_img_1",
                "correlation_id": "corr_doc_img_1",
                "trace_id": "trace_doc_img_1",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["outcome"], "delivered")
        self.assertTrue(payload["candidate_created"])
        self.assertEqual(payload["analysis"]["summary_title"], "Contract clause needs attention")
        self.assertGreater(payload["analysis"]["source_confidence"], 0.5)

    def test_document_analysis_read_model_endpoints_return_persisted_analysis(self) -> None:
        client = TestClient(create_app())

        response = client.post(
            "/api/simulations/documents/contract-review",
            json={
                "user_id": "user_1",
                "session_id": "session_analysis_1",
                "document_text": (
                    "Contrato com renovacao automatica, multa de cancelamento "
                    "e fidelidade de 12 meses."
                ),
                "confidence": 0.92,
                "mode": "balanced",
                "recent_category_count": 0,
                "observation_id": "obs_doc_analysis_1",
                "correlation_id": "corr_doc_analysis_1",
                "trace_id": "trace_doc_analysis_1",
            },
        )
        payload = response.json()
        analysis_id = payload["analysis_id"]

        list_response = client.get("/api/sessions/session_analysis_1/document-analyses")
        detail_response = client.get(f"/api/document-analyses/{analysis_id}")

        self.assertEqual(list_response.status_code, 200)
        list_payload = list_response.json()
        self.assertEqual(len(list_payload), 1)
        self.assertEqual(list_payload[0]["analysis_id"], analysis_id)
        self.assertEqual(list_payload[0]["trace_id"], "trace_doc_analysis_1")

        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()
        self.assertEqual(detail_payload["analysis_id"], analysis_id)
        self.assertEqual(
            detail_payload["analysis"]["summary_title"],
            "Contract clause needs attention",
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

        document_text = (
            "Contrato com renovacao automatica, multa de cancelamento "
            "e fidelidade de 12 meses."
        )
        first_response = client.post(
            "/api/jobs/documents/contract-analysis",
            json={
                "user_id": "user_1",
                "session_id": "session_jobs",
                "artifact_label": "gym-contract.pdf",
                "source_type": "pwa_upload",
                "idempotency_key": "idem_contract_123",
                "document_text": document_text,
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
                "document_text": document_text,
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
        self.assertTrue(app.state.runtime.document_job_worker.wait_until_idle())

        status_response = client.get(f"/api/jobs/{first_payload['job_id']}")

        self.assertEqual(status_response.status_code, 200)
        status_payload = status_response.json()
        self.assertEqual(status_payload["job_id"], first_payload["job_id"])
        self.assertEqual(status_payload["status"], "succeeded")
        self.assertEqual(status_payload["attempts"], 1)
        self.assertIsNotNone(status_payload["result_id"])
        self.assertEqual(status_payload["metadata"]["artifact_label"], "gym-contract.pdf")

    def test_document_analysis_job_worker_completes_and_result_endpoint_returns_analysis(self) -> None:
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
                "document_text": (
                    "Contrato com renovacao automatica, multa de cancelamento "
                    "e fidelidade de 12 meses."
                ),
                "observation_id": "obs_doc_job_1",
                "correlation_id": "corr_jobs_1",
                "trace_id": "trace_jobs_1",
            },
        )
        job_id = enqueue_response.json()["job_id"]

        self.assertTrue(app.state.runtime.document_job_worker.wait_until_idle())
        status_response = client.get(f"/api/jobs/{job_id}")
        result_response = client.get(f"/api/jobs/{job_id}/result")
        trace_response = client.get("/api/sessions/session_jobs/trace")

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(result_response.status_code, 200)
        status_payload = status_response.json()
        result_payload = result_response.json()
        self.assertEqual(status_payload["status"], "succeeded")
        self.assertEqual(status_payload["result_id"], result_payload["analysis_id"])
        self.assertEqual(result_payload["analysis"]["summary_title"], "Contract clause needs attention")
        self.assertEqual(trace_response.status_code, 200)
        self.assertEqual(
            [entry["event_type"] for entry in trace_response.json()["session_trace"]],
            [
                "job_started",
                "job_status_updated",
                "observation_created",
                "alert_candidate_created",
                "alert_shown",
                "lens_command_delivered",
                "job_completed",
            ],
        )

    def test_document_analysis_job_success_requires_persisted_analysis_id(self) -> None:
        app = create_app()
        client = TestClient(app)

        job = app.state.runtime.document_job_enqueuer.execute(
            user_id="user_1",
            session_id="session_jobs_missing_analysis",
            artifact_label="gym-contract.pdf",
            source_type="pwa_upload",
            idempotency_key="idem_contract_789",
            correlation_id="corr_jobs_1",
            trace_id="trace_jobs_1",
        )
        client.post(
            f"/api/jobs/{job.job_id}/status",
            json={
                "target_status": "running",
                "correlation_id": "corr_jobs_2",
                "trace_id": "trace_jobs_1",
            },
        )

        success_response = client.post(
            f"/api/jobs/{job.job_id}/status",
            json={
                "target_status": "succeeded",
                "correlation_id": "corr_jobs_3",
                "trace_id": "trace_jobs_1",
            },
        )

        self.assertEqual(success_response.status_code, 400)
        self.assertEqual(
            success_response.json()["detail"],
            "analysis_id is required when completing document analysis jobs",
        )

    def test_document_analysis_job_endpoint_requires_document_input(self) -> None:
        client = TestClient(create_app())

        response = client.post(
            "/api/jobs/documents/contract-analysis",
            json={
                "user_id": "user_1",
                "session_id": "session_jobs_missing_input",
                "artifact_label": "gym-contract.pdf",
                "source_type": "pwa_upload",
                "idempotency_key": "idem_contract_no_input",
                "correlation_id": "corr_jobs_1",
                "trace_id": "trace_jobs_1",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            "document_text_or_document_image_base64_required",
        )

    def test_lens_feedback_endpoint_records_feedback_for_delivered_command(self) -> None:
        app = create_app()
        client = TestClient(app)

        simulation_response = client.post(
            "/api/simulations/grocery/missing-item",
            json={
                "user_id": "user_feedback",
                "session_id": "session_feedback",
                "item_name": "eggs",
                "confidence": 0.88,
                "mode": "balanced",
                "recent_category_count": 0,
                "observation_id": "obs_feedback_1",
                "correlation_id": "corr_feedback_1",
                "trace_id": "trace_feedback_1",
            },
        )
        command_id = simulation_response.json()["command"]["command_id"]

        feedback_response = client.post(
            f"/api/lens-commands/{command_id}/feedback",
            json={
                "user_id": "user_feedback",
                "session_id": "session_feedback",
                "feedback": "useful",
                "correlation_id": "corr_feedback_2",
                "trace_id": "trace_feedback_1",
            },
        )
        trace_response = client.get(
            "/api/sessions/session_feedback/trace?trace_id=trace_feedback_1"
        )

        self.assertEqual(feedback_response.status_code, 200)
        self.assertEqual(feedback_response.json()["command_id"], command_id)
        self.assertEqual(feedback_response.json()["feedback"], "useful")
        self.assertEqual(
            [entry["event_type"] for entry in trace_response.json()["session_trace"]],
            [
                "observation_created",
                "alert_candidate_created",
                "alert_shown",
                "lens_command_delivered",
                "alert_feedback_given",
            ],
        )
        self.assertEqual(trace_response.json()["session_trace"][-1]["step"], "feedback")

    def test_lens_feedback_endpoint_rejects_command_not_owned_by_session(self) -> None:
        app = create_app()
        client = TestClient(app)

        simulation_response = client.post(
            "/api/simulations/grocery/missing-item",
            json={
                "user_id": "user_feedback",
                "session_id": "session_feedback",
                "item_name": "eggs",
                "confidence": 0.88,
                "mode": "balanced",
                "recent_category_count": 0,
                "observation_id": "obs_feedback_1",
                "correlation_id": "corr_feedback_1",
                "trace_id": "trace_feedback_1",
            },
        )
        command_id = simulation_response.json()["command"]["command_id"]

        feedback_response = client.post(
            f"/api/lens-commands/{command_id}/feedback",
            json={
                "user_id": "other_user",
                "session_id": "session_feedback",
                "feedback": "not_useful",
                "correlation_id": "corr_feedback_2",
                "trace_id": "trace_feedback_1",
            },
        )

        self.assertEqual(feedback_response.status_code, 404)
        self.assertEqual(feedback_response.json()["detail"], "lens_command_not_found")
