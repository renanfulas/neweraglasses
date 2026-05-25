from __future__ import annotations

import base64
import io
import time
from tempfile import TemporaryDirectory
from unittest import TestCase

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from new_era.infrastructure.http.app import create_app


class HttpAppTest(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.app = create_app(storage_path=f"{self.temp_dir.name}\\runtime.sqlite3")
        self.client_cm = TestClient(self.app)
        self.client = self.client_cm.__enter__()

    def tearDown(self) -> None:
        self.app.state.runtime.document_job_worker.wait_until_idle(timeout_seconds=2.0)
        self.client_cm.__exit__(None, None, None)
        self.temp_dir.cleanup()

    def test_root_serves_pwa_shell(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("New Era Glasses", response.text)
        self.assertIn("Localhost runtime", response.text)

    def test_health_endpoint_returns_ok(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_device_capabilities_endpoint_reports_runtime_gateway(self) -> None:
        response = self.client.get("/api/device/capabilities")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["adapter_name"], "browser_simulation")
        self.assertTrue(payload["supports_camera"])
        self.assertTrue(payload["supports_display"])

    def test_manifest_endpoint_is_available(self) -> None:
        response = self.client.get("/manifest.webmanifest")
        self.assertEqual(response.status_code, 200)
        self.assertIn("New Era Glasses", response.text)

    def test_grocery_simulation_endpoint_returns_suppressed_for_low_confidence(self) -> None:
        response = self.client.post(
            "/api/simulations/grocery/missing-item",
            json={
                "user_id": "user_1",
                "session_id": "session_grocery_low",
                "item_name": "eggs",
                "confidence": 0.2,
                "mode": "balanced",
                "recent_category_count": 0,
                "observation_id": "obs_grocery_low",
                "correlation_id": "corr_grocery_low",
                "trace_id": "trace_grocery_low",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["outcome"], "suppressed")
        self.assertTrue(payload["candidate_created"])
        self.assertIsNone(payload["command"])

    def test_document_contract_review_endpoint_processes_risk_signal(self) -> None:
        response = self.client.post(
            "/api/simulations/documents/contract-review",
            json={
                "user_id": "user_1",
                "session_id": "session_contract_risk",
                "document_text": (
                    "Plano com fidelidade de 12 meses, renovacao automatica por igual "
                    "periodo e multa de cancelamento antecipado."
                ),
                "trace_id": "trace_contract_risk",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["outcome"], "delivered")
        self.assertTrue(payload["candidate_created"])
        self.assertTrue(payload["analysis_id"])
        self.assertGreaterEqual(len(payload["analysis"]["findings"]), 3)

    def test_document_contract_review_endpoint_returns_observation_only_when_no_risk_is_found(self) -> None:
        response = self.client.post(
            "/api/simulations/documents/contract-review",
            json={
                "user_id": "user_1",
                "session_id": "session_contract_safe",
                "document_text": "Horario de atendimento de segunda a sexta feira em horario comercial.",
                "trace_id": "trace_contract_safe",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["outcome"], "suppressed")
        self.assertFalse(payload["candidate_created"])
        self.assertIn("No obvious high-risk clause", payload["analysis"]["summary_body"])

    def test_document_contract_review_endpoint_supports_image_ocr(self) -> None:
        response = self.client.post(
            "/api/simulations/documents/contract-review",
            json={
                "user_id": "user_1",
                "session_id": "session_contract_image",
                "document_image_base64": self._build_contract_image_base64(),
                "trace_id": "trace_contract_image",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["analysis_id"])
        self.assertIn("summary_title", payload["analysis"])

    def test_camera_bridge_contract_review_processes_real_camera_image(self) -> None:
        response = self.client.post(
            "/api/device-bridge/camera/document-contract-review",
            json={
                "user_id": "user_camera",
                "session_id": "session_camera_contract",
                "image_base64": self._build_contract_image_base64(),
                "content_type": "image/png",
                "source_adapter": "phone_camera",
                "trace_id": "trace_camera_contract",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["outcome"], "delivered")
        self.assertTrue(payload["candidate_created"])
        self.assertEqual(payload["analysis"]["summary_title"], "Contract clause needs attention")

    def test_camera_bridge_contract_review_rejects_unsupported_content_type(self) -> None:
        response = self.client.post(
            "/api/device-bridge/camera/document-contract-review",
            json={
                "user_id": "user_camera",
                "image_base64": self._build_contract_image_base64(),
                "content_type": "application/pdf",
                "source_adapter": "phone_camera",
            },
        )
        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.json()["detail"], "unsupported_camera_content_type")

    def test_document_analysis_read_model_endpoints_return_persisted_analysis(self) -> None:
        simulation = self.client.post(
            "/api/simulations/documents/contract-review",
            json={
                "user_id": "user_1",
                "session_id": "session_analysis_read",
                "document_text": "Contrato com multa e fidelidade de 12 meses.",
                "trace_id": "trace_analysis_read",
            },
        ).json()
        analysis_id = simulation["analysis_id"]

        detail = self.client.get(f"/api/document-analyses/{analysis_id}")
        listing = self.client.get("/api/sessions/session_analysis_read/document-analyses")

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["analysis_id"], analysis_id)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()[0]["analysis_id"], analysis_id)

    def test_session_trace_endpoint_reads_persisted_trace_for_same_app_runtime(self) -> None:
        self.client.post(
            "/api/simulations/grocery/missing-item",
            json={
                "user_id": "user_1",
                "session_id": "session_trace_http",
                "item_name": "eggs",
                "confidence": 0.88,
                "mode": "balanced",
                "recent_category_count": 0,
                "observation_id": "obs_trace_http",
                "correlation_id": "corr_trace_http",
                "trace_id": "trace_trace_http",
            },
        )

        response = self.client.get(
            "/api/sessions/session_trace_http/trace",
            params={"trace_id": "trace_trace_http"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["event_count"], 4)
        self.assertEqual(payload["session_trace"][0]["step"], "observation")

    def test_user_session_endpoints_create_list_and_filter_trace(self) -> None:
        created = self.client.post(
            "/api/users/user_sessions_http/sessions",
            json={"module": "documents", "title": "Docs Session"},
        )
        self.assertEqual(created.status_code, 200)
        session_id = created.json()["session_id"]

        self.client.post(
            "/api/simulations/documents/contract-review",
            json={
                "user_id": "user_sessions_http",
                "session_id": session_id,
                "document_text": "Contrato com multa e fidelidade de 12 meses.",
                "trace_id": "trace_user_sessions_http",
            },
        )

        sessions = self.client.get("/api/users/user_sessions_http/sessions", params={"module": "documents"})
        scoped_trace = self.client.get(
            f"/api/users/user_sessions_http/sessions/{session_id}/trace",
            params={"trace_id": "trace_user_sessions_http", "step": "decision"},
        )

        self.assertEqual(sessions.status_code, 200)
        self.assertEqual(sessions.json()["session_count"], 1)
        self.assertEqual(scoped_trace.status_code, 200)
        self.assertEqual(scoped_trace.json()["session_trace"][0]["step"], "decision")

    def test_user_scoped_trace_rejects_other_user_session(self) -> None:
        created = self.client.post(
            "/api/users/user_owner/sessions",
            json={"module": "documents", "session_id": "session_owned_http"},
        )
        self.assertEqual(created.status_code, 200)

        response = self.client.get("/api/users/other_user/sessions/session_owned_http/trace")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "user_session_not_found")

    def test_document_analysis_job_endpoints_support_idempotent_enqueue_and_status(self) -> None:
        payload = {
            "user_id": "user_jobs",
            "session_id": "session_jobs",
            "artifact_label": "gym-contract.pdf",
            "source_type": "pwa_upload",
            "idempotency_key": "idem_contract_123",
            "document_text": "Contrato com multa e fidelidade de 12 meses.",
            "correlation_id": "corr_jobs_1",
            "trace_id": "trace_jobs_1",
        }
        first = self.client.post("/api/jobs/documents/contract-analysis", json=payload)
        second = self.client.post("/api/jobs/documents/contract-analysis", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["job_id"], second.json()["job_id"])

        status_response = self.client.get(f"/api/jobs/{first.json()['job_id']}")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["job_id"], first.json()["job_id"])

    def test_document_analysis_job_worker_completes_and_result_endpoint_returns_analysis(self) -> None:
        enqueue_response = self.client.post(
            "/api/jobs/documents/contract-analysis",
            json={
                "user_id": "user_jobs_success",
                "session_id": "session_jobs_success",
                "artifact_label": "gym-contract.pdf",
                "source_type": "pwa_upload",
                "idempotency_key": "idem_contract_456",
                "document_text": "Contrato com multa e fidelidade de 12 meses.",
                "correlation_id": "corr_jobs_1",
                "trace_id": "trace_jobs_1",
            },
        )
        self.assertEqual(enqueue_response.status_code, 200)
        job_id = enqueue_response.json()["job_id"]
        final_job = self._wait_for_job(job_id)

        result_response = self.client.get(f"/api/jobs/{job_id}/result")
        self.assertEqual(final_job["status"], "succeeded")
        self.assertEqual(result_response.status_code, 200)
        self.assertEqual(result_response.json()["analysis_id"], final_job["result_id"])

    def test_document_analysis_job_success_requires_persisted_analysis_id(self) -> None:
        enqueue_response = self.client.post(
            "/api/jobs/documents/contract-analysis",
            json={
                "user_id": "user_1",
                "session_id": "session_jobs_missing_analysis",
                "artifact_label": "gym-contract.pdf",
                "source_type": "pwa_upload",
                "idempotency_key": "idem_contract_789",
                "correlation_id": "corr_jobs_1",
                "trace_id": "trace_jobs_1",
                "document_text": "Contrato com multa e fidelidade de 12 meses.",
            },
        )
        job_id = enqueue_response.json()["job_id"]
        self.client.post(
            f"/api/jobs/{job_id}/status",
            json={
                "target_status": "running",
                "correlation_id": "corr_jobs_2",
                "trace_id": "trace_jobs_1",
            },
        )
        success_response = self.client.post(
            f"/api/jobs/{job_id}/status",
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
        response = self.client.post(
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
        simulation_response = self.client.post(
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

        feedback_response = self.client.post(
            f"/api/lens/commands/{command_id}/feedback",
            json={
                "user_id": "user_feedback",
                "session_id": "session_feedback",
                "feedback": "useful",
                "correlation_id": "corr_feedback_2",
                "trace_id": "trace_feedback_1",
            },
        )
        trace_response = self.client.get(
            "/api/sessions/session_feedback/trace",
            params={"trace_id": "trace_feedback_1"},
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
        simulation_response = self.client.post(
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

        feedback_response = self.client.post(
            f"/api/lens/commands/{command_id}/feedback",
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

    def _build_contract_image_base64(self) -> str:
        image = Image.new("RGB", (1400, 500), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        draw.text(
            (40, 60),
            "renovacao automatica multa fidelidade",
            fill="black",
            font=font,
        )
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")

    def _wait_for_job(self, job_id: str) -> dict[str, object]:
        for _ in range(40):
            response = self.client.get(f"/api/jobs/{job_id}")
            payload = response.json()
            if payload["status"] in {"succeeded", "failed"}:
                return payload
            time.sleep(0.05)
        self.fail(f"job {job_id} did not reach a terminal state")
