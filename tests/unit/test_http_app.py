import base64
import io
import time
from unittest import TestCase

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from new_era.domain.jobs import JobStatus
from new_era.infrastructure.http.app import create_app


class HttpAppTest(TestCase):
    @staticmethod
    def _auth_headers(user_id: str) -> dict[str, str]:
        return {"X-New-Era-User-Id": user_id}

    def test_root_serves_pwa_shell(self) -> None:
        client = TestClient(create_app())

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Context, attention, and display in one loop.", response.text)
        self.assertIn("Contracts", response.text)

    def test_analysis_detail_route_serves_pwa_shell(self) -> None:
        client = TestClient(create_app())

        response = client.get("/document-analyses/analysis_demo/view")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Contracts Session Library", response.text)

    def test_health_endpoint_returns_ok(self) -> None:
        client = TestClient(create_app())

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_device_capabilities_endpoint_reports_runtime_gateway(self) -> None:
        client = TestClient(create_app())

        response = client.get("/api/device/capabilities")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["adapter_name"], "browser_simulation")
        self.assertTrue(payload["supports_camera"])
        self.assertTrue(payload["supports_display"])

    def test_manifest_endpoint_is_available(self) -> None:
        client = TestClient(create_app())

        response = client.get("/manifest.webmanifest")

        self.assertEqual(response.status_code, 200)
        self.assertIn('"name": "New Era Simulator"', response.text)

    def test_grocery_simulation_endpoint_processes_missing_item(self) -> None:
        client = TestClient(create_app(), headers=self._auth_headers("user_1"))

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
        client = TestClient(create_app(), headers=self._auth_headers("user_1"))

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
        client = TestClient(create_app(), headers=self._auth_headers("user_1"))

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
        self.assertNotIn("extracted_text", payload["analysis"])
        self.assertIn("automatic_renewal", str(payload["analysis"]["findings"][0]["finding_type"]))
        self.assertEqual(
            [entry["step"] for entry in payload["session_trace"]],
            ["observation", "candidate", "decision", "delivery"],
        )

    def test_document_contract_review_endpoint_returns_observation_only_when_no_risk_is_found(self) -> None:
        client = TestClient(create_app(), headers=self._auth_headers("user_1"))

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
        client = TestClient(create_app(), headers=self._auth_headers("user_1"))
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

    def test_camera_bridge_contract_review_processes_real_camera_image(self) -> None:
        client = TestClient(create_app(), headers=self._auth_headers("user_camera"))
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
            "/api/device-bridge/camera/document-contract-review",
            json={
                "user_id": "user_camera",
                "session_id": "session_camera",
                "image_base64": image_base64,
                "content_type": "image/png",
                "source_adapter": "phone_camera",
                "mode": "balanced",
                "recent_category_count": 0,
                "observation_id": "obs_camera_1",
                "correlation_id": "corr_camera_1",
                "trace_id": "trace_camera_1",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["outcome"], "delivered")
        self.assertTrue(payload["candidate_created"])
        self.assertEqual(payload["delivered_commands_count"], 1)
        self.assertIsNotNone(payload["analysis_id"])
        self.assertEqual(payload["analysis"]["summary_title"], "Contract clause needs attention")
        self.assertEqual(
            [entry["event_type"] for entry in payload["session_trace"]],
            [
                "observation_created",
                "alert_candidate_created",
                "alert_shown",
                "lens_command_delivered",
            ],
        )
        self.assertIn("camera bridge", payload["session_trace"][0]["detail"])

        analysis_response = client.get(f"/api/document-analyses/{payload['analysis_id']}")

        self.assertEqual(analysis_response.status_code, 200)
        self.assertEqual(analysis_response.json()["source_type"], "camera:phone_camera")

    def test_camera_bridge_contract_review_rejects_unsupported_content_type(self) -> None:
        client = TestClient(create_app(), headers=self._auth_headers("user_camera"))

        response = client.post(
            "/api/device-bridge/camera/document-contract-review",
            json={
                "user_id": "user_camera",
                "session_id": "session_camera",
                "image_base64": "not-an-image",
                "content_type": "application/octet-stream",
            },
        )

        self.assertEqual(response.status_code, 415)
        self.assertEqual(
            response.json()["detail"]["code"],
            "unsupported_camera_content_type",
        )

    def test_document_analysis_read_model_endpoints_return_persisted_analysis(self) -> None:
        client = TestClient(create_app(), headers=self._auth_headers("user_1"))

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
        self.assertNotIn("extracted_text", detail_payload["analysis"])
        self.assertIsNone(detail_payload["feedback"])

    def test_document_analysis_feedback_endpoint_persists_feedback_and_enriches_read_models(self) -> None:
        client = TestClient(create_app(), headers=self._auth_headers("user_1"))

        response = client.post(
            "/api/simulations/documents/contract-review",
            json={
                "user_id": "user_1",
                "session_id": "session_analysis_feedback_1",
                "document_text": (
                    "Contrato com renovacao automatica, multa de cancelamento "
                    "e fidelidade de 12 meses."
                ),
                "confidence": 0.92,
                "mode": "balanced",
                "recent_category_count": 0,
                "observation_id": "obs_doc_analysis_feedback_1",
                "correlation_id": "corr_doc_analysis_feedback_1",
                "trace_id": "trace_doc_analysis_feedback_1",
            },
        )
        analysis_id = response.json()["analysis_id"]

        feedback_response = client.post(
            f"/api/document-analyses/{analysis_id}/feedback",
            json={
                "user_id": "user_1",
                "session_id": "session_analysis_feedback_1",
                "feedback": "useful",
                "correlation_id": "corr_analysis_feedback_2",
                "trace_id": "trace_doc_analysis_feedback_1",
            },
        )
        detail_response = client.get(f"/api/document-analyses/{analysis_id}")
        list_response = client.get("/api/sessions/session_analysis_feedback_1/document-analyses")
        trace_response = client.get(
            "/api/sessions/session_analysis_feedback_1/trace?trace_id=trace_doc_analysis_feedback_1"
        )

        self.assertEqual(feedback_response.status_code, 200)
        self.assertEqual(feedback_response.json()["analysis_id"], analysis_id)
        self.assertEqual(feedback_response.json()["feedback"], "useful")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["feedback"], "useful")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()[0]["feedback"], "useful")
        self.assertEqual(
            trace_response.json()["session_trace"][-1]["event_type"],
            "document_analysis_feedback_given",
        )

    def test_document_feedback_metrics_endpoint_returns_session_aggregates(self) -> None:
        client = TestClient(create_app(), headers=self._auth_headers("user_metrics"))

        first_response = client.post(
            "/api/simulations/documents/contract-review",
            json={
                "user_id": "user_metrics",
                "session_id": "session_metrics",
                "document_text": (
                    "Contrato com renovacao automatica, multa de cancelamento "
                    "e fidelidade de 12 meses."
                ),
                "observation_id": "obs_metrics_1",
                "correlation_id": "corr_metrics_1",
                "trace_id": "trace_metrics_1",
            },
        )
        second_response = client.post(
            "/api/simulations/documents/contract-review",
            json={
                "user_id": "user_metrics",
                "session_id": "session_metrics",
                "document_text": "Horario de atendimento de segunda a sexta.",
                "observation_id": "obs_metrics_2",
                "correlation_id": "corr_metrics_2",
                "trace_id": "trace_metrics_2",
            },
        )

        first_analysis_id = first_response.json()["analysis_id"]
        second_analysis_id = second_response.json()["analysis_id"]

        client.post(
            f"/api/document-analyses/{first_analysis_id}/feedback",
            json={
                "user_id": "user_metrics",
                "session_id": "session_metrics",
                "feedback": "not_useful",
                "correlation_id": "corr_metrics_feedback_1",
                "trace_id": "trace_metrics_1",
            },
        )
        client.post(
            f"/api/document-analyses/{second_analysis_id}/feedback",
            json={
                "user_id": "user_metrics",
                "session_id": "session_metrics",
                "feedback": "useful",
                "correlation_id": "corr_metrics_feedback_2",
                "trace_id": "trace_metrics_2",
            },
        )

        response = client.get(
            "/api/users/user_metrics/sessions/session_metrics/feedback-metrics"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["user_id"], "user_metrics")
        self.assertEqual(payload["session_id"], "session_metrics")
        self.assertEqual(payload["aggregate"]["analysis_count"], 2)
        self.assertEqual(payload["aggregate"]["feedback_count"], 2)
        self.assertEqual(payload["aggregate"]["useful_feedback_count"], 1)
        self.assertEqual(payload["aggregate"]["not_useful_feedback_count"], 1)
        finding_types = {
            entry["finding_type"]: entry
            for entry in payload["by_finding_type"]
        }
        self.assertEqual(
            finding_types["automatic_renewal"]["not_useful_feedback_count"],
            1,
        )

    def test_document_feedback_metrics_endpoint_hides_foreign_session(self) -> None:
        app = create_app()
        owner_client = TestClient(app, headers=self._auth_headers("owner_metrics"))
        foreign_client = TestClient(app, headers=self._auth_headers("other_metrics"))

        owner_client.post(
            "/api/simulations/documents/contract-review",
            json={
                "user_id": "owner_metrics",
                "session_id": "session_metrics_hidden",
                "document_text": "Contrato com renovacao automatica.",
                "observation_id": "obs_metrics_hidden_1",
                "correlation_id": "corr_metrics_hidden_1",
                "trace_id": "trace_metrics_hidden_1",
            },
        )

        response = foreign_client.get(
            "/api/users/other_metrics/sessions/session_metrics_hidden/feedback-metrics"
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "session_not_found")

    def test_session_trace_endpoint_reads_persisted_trace_for_same_app_runtime(self) -> None:
        app = create_app()
        client = TestClient(app, headers=self._auth_headers("user_1"))

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

    def test_user_session_endpoints_create_list_and_filter_trace(self) -> None:
        app = create_app()
        client = TestClient(app, headers=self._auth_headers("user_sessions"))

        create_response = client.post(
            "/api/users/user_sessions/sessions",
            json={
                "module": "grocery",
                "title": "Weekend groceries",
            },
        )
        session_id = create_response.json()["session_id"]
        client.post(
            "/api/simulations/grocery/missing-item",
            json={
                "user_id": "user_sessions",
                "session_id": session_id,
                "item_name": "eggs",
                "confidence": 0.88,
                "mode": "balanced",
                "recent_category_count": 0,
                "observation_id": "obs_user_session_1",
                "correlation_id": "corr_user_session_1",
                "trace_id": "trace_user_session_1",
            },
        )

        list_response = client.get("/api/users/user_sessions/sessions?module=grocery")
        trace_response = client.get(
            f"/api/users/user_sessions/sessions/{session_id}/trace"
            "?module=grocery&step=decision"
        )

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["session_count"], 1)
        self.assertEqual(list_response.json()["sessions"][0]["session_id"], session_id)
        self.assertEqual(trace_response.status_code, 200)
        self.assertEqual(trace_response.json()["event_count"], 1)
        self.assertEqual(
            trace_response.json()["session_trace"][0]["event_type"],
            "alert_shown",
        )

    def test_user_scoped_trace_rejects_other_user_session(self) -> None:
        app = create_app()
        client = TestClient(app, headers=self._auth_headers("user_owner"))

        create_response = client.post(
            "/api/users/user_owner/sessions",
            json={"module": "grocery"},
        )
        session_id = create_response.json()["session_id"]

        response = client.get(
            f"/api/users/other_user/sessions/{session_id}/trace",
            headers=self._auth_headers("other_user"),
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "session_not_found")

    def test_document_analysis_job_endpoints_support_idempotent_enqueue_and_status(self) -> None:
        app = create_app()
        client = TestClient(app, headers=self._auth_headers("user_1"))

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

    def test_session_jobs_endpoint_lists_user_owned_jobs(self) -> None:
        app = create_app()
        client = TestClient(app, headers=self._auth_headers("user_jobs"))

        client.post(
            "/api/jobs/documents/contract-analysis",
            json={
                "user_id": "user_jobs",
                "session_id": "session_jobs_list",
                "artifact_label": "contract-a.pdf",
                "source_type": "pwa_upload",
                "idempotency_key": "idem_contract_list_a",
                "document_text": (
                    "Contrato com renovacao automatica, multa de cancelamento "
                    "e fidelidade de 12 meses."
                ),
                "correlation_id": "corr_jobs_list_1",
                "trace_id": "trace_jobs_list_1",
            },
        )
        time.sleep(0.01)
        client.post(
            "/api/jobs/documents/contract-analysis",
            json={
                "user_id": "user_jobs",
                "session_id": "session_jobs_list",
                "artifact_label": "contract-b.pdf",
                "source_type": "pwa_upload",
                "idempotency_key": "idem_contract_list_b",
                "document_text": (
                    "Contrato com renovacao automatica, multa de cancelamento "
                    "e fidelidade de 12 meses."
                ),
                "correlation_id": "corr_jobs_list_2",
                "trace_id": "trace_jobs_list_2",
            },
        )
        self.assertTrue(app.state.runtime.document_job_worker.wait_until_idle())

        response = client.get(
            "/api/users/user_jobs/sessions/session_jobs_list/jobs?module=documents&limit=10"
        )
        other_user_response = client.get(
            "/api/users/other_user/sessions/session_jobs_list/jobs?module=documents",
            headers=self._auth_headers("other_user"),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["job_count"], 2)
        self.assertEqual(payload["jobs"][0]["status"], "succeeded")
        self.assertEqual(payload["jobs"][0]["metadata"]["artifact_label"], "contract-b.pdf")
        self.assertEqual(other_user_response.status_code, 404)
        self.assertEqual(other_user_response.json()["detail"], "session_not_found")

    def test_session_jobs_endpoint_includes_recent_blocked_reason(self) -> None:
        app = create_app()
        client = TestClient(app, headers=self._auth_headers("user_jobs_blocked"))

        for index in range(5):
            app.state.runtime.document_job_enqueuer.execute(
                user_id="user_jobs_blocked",
                session_id="session_jobs_blocked",
                artifact_label=f"contract-{index}.pdf",
                source_type="pwa_upload",
                idempotency_key=f"idem_jobs_blocked_{index}",
                document_text=(
                    "Contrato com renovacao automatica, multa de cancelamento "
                    "e fidelidade de 12 meses."
                ),
                correlation_id=f"corr_jobs_blocked_{index}",
                trace_id=f"trace_jobs_blocked_{index}",
            )

        blocked_response = client.post(
            "/api/jobs/documents/contract-analysis",
            json={
                "user_id": "user_jobs_blocked",
                "session_id": "session_jobs_blocked",
                "artifact_label": "contract-overflow.pdf",
                "source_type": "pwa_upload",
                "idempotency_key": "idem_jobs_blocked_overflow",
                "document_text": (
                    "Contrato com renovacao automatica, multa de cancelamento "
                    "e fidelidade de 12 meses."
                ),
                "correlation_id": "corr_jobs_blocked_overflow",
                "trace_id": "trace_jobs_blocked_overflow",
            },
        )
        jobs_response = client.get(
            "/api/users/user_jobs_blocked/sessions/session_jobs_blocked/jobs?module=documents&limit=10"
        )

        self.assertEqual(blocked_response.status_code, 429)
        self.assertEqual(jobs_response.status_code, 200)
        payload = jobs_response.json()
        self.assertEqual(payload["job_count"], 5)
        self.assertEqual(
            payload["blocked_reason"]["code"],
            "session_active_job_limit_exceeded",
        )
        self.assertEqual(payload["blocked_reason"]["reason"], "quota_exceeded")

    def test_session_jobs_endpoint_clears_blocked_reason_after_session_recovers(self) -> None:
        app = create_app()
        client = TestClient(app, headers=self._auth_headers("user_jobs_recovered"))

        queued_jobs: list[str] = []
        for index in range(5):
            job = app.state.runtime.document_job_enqueuer.execute(
                user_id="user_jobs_recovered",
                session_id="session_jobs_recovered",
                artifact_label=f"contract-{index}.pdf",
                source_type="pwa_upload",
                idempotency_key=f"idem_jobs_recovered_{index}",
                document_text=(
                    "Contrato com renovacao automatica, multa de cancelamento "
                    "e fidelidade de 12 meses."
                ),
                correlation_id=f"corr_jobs_recovered_{index}",
                trace_id=f"trace_jobs_recovered_{index}",
            )
            queued_jobs.append(job.job_id)

        blocked_response = client.post(
            "/api/jobs/documents/contract-analysis",
            json={
                "user_id": "user_jobs_recovered",
                "session_id": "session_jobs_recovered",
                "artifact_label": "contract-overflow.pdf",
                "source_type": "pwa_upload",
                "idempotency_key": "idem_jobs_recovered_overflow",
                "document_text": (
                    "Contrato com renovacao automatica, multa de cancelamento "
                    "e fidelidade de 12 meses."
                ),
                "correlation_id": "corr_jobs_recovered_overflow",
                "trace_id": "trace_jobs_recovered_overflow",
            },
        )
        app.state.runtime.document_job_advancer.execute(
            job_id=queued_jobs[0],
            target_status=JobStatus.FAILED,
            correlation_id="corr_jobs_recovered_clear",
            trace_id="trace_jobs_recovered_clear",
            error_code="manual_failure",
            error_message="operator cleared queue",
        )
        jobs_response = client.get(
            "/api/users/user_jobs_recovered/sessions/session_jobs_recovered/jobs?module=documents&limit=10"
        )

        self.assertEqual(blocked_response.status_code, 429)
        self.assertEqual(jobs_response.status_code, 200)
        payload = jobs_response.json()
        self.assertEqual(payload["job_count"], 5)
        self.assertIsNone(payload["blocked_reason"])

    def test_document_analysis_job_worker_completes_and_result_endpoint_returns_analysis(self) -> None:
        app = create_app()
        client = TestClient(app, headers=self._auth_headers("user_1"))

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
        self.assertNotIn("extracted_text", result_payload["analysis"])
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

    def test_document_analysis_job_worker_accepts_uploaded_image_payload(self) -> None:
        app = create_app()
        client = TestClient(app, headers=self._auth_headers("user_image_job"))
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

        enqueue_response = client.post(
            "/api/jobs/documents/contract-analysis",
            json={
                "user_id": "user_image_job",
                "session_id": "session_image_jobs",
                "artifact_label": "camera-capture.png",
                "source_type": "pwa_camera_or_upload",
                "idempotency_key": "idem_image_contract_456",
                "document_image_base64": image_base64,
                "observation_id": "obs_doc_image_job_1",
                "correlation_id": "corr_image_jobs_1",
                "trace_id": "trace_image_jobs_1",
            },
        )
        job_id = enqueue_response.json()["job_id"]

        self.assertEqual(enqueue_response.status_code, 200)
        self.assertTrue(app.state.runtime.document_job_worker.wait_until_idle(timeout_seconds=15))
        status_response = client.get(f"/api/jobs/{job_id}")
        result_response = client.get(f"/api/jobs/{job_id}/result")

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(result_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "succeeded")
        self.assertEqual(status_response.json()["metadata"]["source_type"], "pwa_camera_or_upload")
        self.assertEqual(
            result_response.json()["analysis"]["summary_title"],
            "Contract clause needs attention",
        )

    def test_multipart_document_upload_creates_job_and_local_artifact(self) -> None:
        app = create_app()
        client = TestClient(app, headers=self._auth_headers("user_upload_job"))
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
        upload_bytes = buffer.getvalue()

        response = client.post(
            "/api/uploads/documents/contract-analysis",
            data={
                "user_id": "user_upload_job",
                "session_id": "session_upload_jobs",
                "idempotency_key": "idem_upload_contract_456",
                "mode": "balanced",
                "recent_category_count": "0",
                "observation_id": "obs_doc_upload_job_1",
                "correlation_id": "corr_upload_jobs_1",
                "trace_id": "trace_upload_jobs_1",
            },
            files={
                "artifact": ("camera-capture.png", upload_bytes, "image/png"),
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "queued")
        self.assertEqual(payload["metadata"]["artifact_label"], "camera-capture.png")
        self.assertTrue(payload["metadata"]["artifact_id"])
        self.assertEqual(payload["metadata"]["source_type"], "pwa_multipart_upload")
        self.assertTrue(any(app.state.upload_dir.iterdir()))

        self.assertTrue(app.state.runtime.document_job_worker.wait_until_idle(timeout_seconds=15))
        status_response = client.get(f"/api/jobs/{payload['job_id']}")
        result_response = client.get(f"/api/jobs/{payload['job_id']}/result")

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "succeeded")
        self.assertEqual(result_response.status_code, 200)
        self.assertEqual(
            result_response.json()["artifact_id"],
            payload["metadata"]["artifact_id"],
        )
        self.assertEqual(
            result_response.json()["analysis"]["summary_title"],
            "Contract clause needs attention",
        )

    def test_document_artifact_delete_endpoint_deletes_owned_artifact(self) -> None:
        app = create_app()
        client = TestClient(app, headers=self._auth_headers("user_delete_artifact"))
        image = Image.new("RGB", (640, 180), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=32)
        draw.text((24, 60), "AUTOMATIC RENEWAL", fill="black", font=font)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        upload_response = client.post(
            "/api/uploads/documents/contract-analysis",
            data={
                "user_id": "user_delete_artifact",
                "session_id": "session_delete_artifact",
                "idempotency_key": "idem_delete_artifact_001",
            },
            files={
                "artifact": ("delete-me.png", buffer.getvalue(), "image/png"),
            },
        )
        artifact_id = upload_response.json()["metadata"]["artifact_id"]

        delete_response = client.delete(f"/api/document-artifacts/{artifact_id}")
        trace_response = client.get("/api/sessions/session_delete_artifact/trace")

        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["artifact_id"], artifact_id)
        self.assertEqual(delete_response.json()["status"], "deleted")
        self.assertFalse(any(app.state.upload_dir.rglob(f"{artifact_id}_*")))
        self.assertEqual(trace_response.status_code, 200)
        self.assertIn(
            "document_uploaded",
            [entry["event_type"] for entry in trace_response.json()["session_trace"]],
        )
        self.assertIn(
            "document_deleted",
            [entry["event_type"] for entry in trace_response.json()["session_trace"]],
        )

    def test_multipart_document_upload_rejects_unsupported_content_type(self) -> None:
        client = TestClient(create_app(), headers=self._auth_headers("user_upload_job"))

        response = client.post(
            "/api/uploads/documents/contract-analysis",
            data={
                "user_id": "user_upload_job",
                "session_id": "session_upload_jobs",
            },
            files={
                "artifact": ("contract.txt", b"plain text contract", "text/plain"),
            },
        )

        self.assertEqual(response.status_code, 415)
        self.assertEqual(
            response.json()["detail"]["code"],
            "unsupported_upload_content_type",
        )

    def test_multipart_document_upload_count_quota_persists_blocked_reason_after_refresh(self) -> None:
        app = create_app()
        client = TestClient(app, headers=self._auth_headers("user_upload_limit"))

        for index in range(20):
            app.state.runtime.document_artifact_registrar.execute(
                user_id="user_upload_limit",
                session_id="session_upload_limit",
                artifact_label=f"contract-{index}.png",
                source_type="seed_upload",
                content_type="image/png",
                payload=b"png-bytes",
                correlation_id=f"corr_upload_limit_seed_{index}",
                trace_id=f"trace_upload_limit_seed_{index}",
            )

        response = client.post(
            "/api/uploads/documents/contract-analysis",
            data={
                "user_id": "user_upload_limit",
                "session_id": "session_upload_limit",
                "idempotency_key": "idem_upload_limit_overflow",
            },
            files={
                "artifact": ("overflow.png", b"new-upload", "image/png"),
            },
        )
        jobs_response = client.get(
            "/api/users/user_upload_limit/sessions/session_upload_limit/jobs?module=documents&limit=10"
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(
            response.json()["detail"]["code"],
            "session_active_artifact_limit_exceeded",
        )
        self.assertEqual(response.json()["detail"]["limit"], 20)
        self.assertEqual(response.json()["detail"]["current"], 20)
        self.assertEqual(jobs_response.status_code, 200)
        self.assertEqual(
            jobs_response.json()["blocked_reason"]["code"],
            "session_active_artifact_limit_exceeded",
        )

    def test_multipart_document_upload_storage_quota_returns_byte_budget_policy_rejection(self) -> None:
        app = create_app()
        client = TestClient(app, headers=self._auth_headers("user_upload_storage_limit"))

        app.state.runtime.document_artifact_registrar.execute(
            user_id="user_upload_storage_limit",
            session_id="session_upload_storage_limit",
            artifact_label="existing-large.png",
            source_type="seed_upload",
            content_type="image/png",
            payload=b"x" * 25_000_000,
            correlation_id="corr_upload_storage_seed",
            trace_id="trace_upload_storage_seed",
        )

        response = client.post(
            "/api/uploads/documents/contract-analysis",
            data={
                "user_id": "user_upload_storage_limit",
                "session_id": "session_upload_storage_limit",
                "idempotency_key": "idem_upload_storage_limit_overflow",
            },
            files={
                "artifact": ("overflow.png", b"0", "image/png"),
            },
        )
        jobs_response = client.get(
            "/api/users/user_upload_storage_limit/sessions/session_upload_storage_limit/jobs?module=documents&limit=10"
        )

        self.assertEqual(response.status_code, 429)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "session_artifact_storage_limit_exceeded")
        self.assertEqual(
            detail["message"],
            "This session reached the local document storage limit.",
        )
        self.assertEqual(detail["limit"], 25_000_000)
        self.assertEqual(detail["current"], 25_000_001)
        self.assertEqual(jobs_response.status_code, 200)
        self.assertEqual(
            jobs_response.json()["blocked_reason"]["code"],
            "session_artifact_storage_limit_exceeded",
        )

    def test_document_analysis_job_success_requires_persisted_analysis_id(self) -> None:
        app = create_app()
        client = TestClient(app, headers=self._auth_headers("user_1"))

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
        client = TestClient(create_app(), headers=self._auth_headers("user_1"))

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
            response.json()["detail"]["code"],
            "document_text_or_document_image_base64_required",
        )

    def test_document_contract_review_requires_local_authenticated_user(self) -> None:
        client = TestClient(create_app())

        response = client.post(
            "/api/simulations/documents/contract-review",
            json={
                "user_id": "user_1",
                "session_id": "session_1",
                "document_text": "Contrato com fidelidade de 12 meses e multa.",
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "local_auth_user_required")

    def test_user_session_endpoint_rejects_authenticated_user_mismatch(self) -> None:
        client = TestClient(create_app(), headers=self._auth_headers("user_owner"))

        response = client.post(
            "/api/users/other_user/sessions",
            json={
                "module": "documents",
                "title": "Contract review session",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "authenticated_user_mismatch")

    def test_lens_feedback_endpoint_records_feedback_for_delivered_command(self) -> None:
        app = create_app()
        client = TestClient(app, headers=self._auth_headers("user_feedback"))

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
        client = TestClient(app, headers=self._auth_headers("user_feedback"))

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
            headers=self._auth_headers("other_user"),
        )

        self.assertEqual(feedback_response.status_code, 404)
        self.assertEqual(feedback_response.json()["detail"], "lens_command_not_found")
