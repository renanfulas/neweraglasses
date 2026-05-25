from __future__ import annotations

import time
import unittest
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from new_era.infrastructure.http import create_app


CONTRACT_TEXT = (
    "Este contrato possui fidelidade de 12 meses, multa de cancelamento "
    "e renovacao automatica ao final do periodo."
)


class HttpSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.database_path = f"{self.temp_dir.name}\\runtime.sqlite3"
        self.client = TestClient(create_app(storage_path=self.database_path))

    def tearDown(self) -> None:
        self.client.close()
        self.temp_dir.cleanup()

    def test_health_root_and_device_capabilities_are_available(self) -> None:
        health = self.client.get("/health")
        root = self.client.get("/")
        capabilities = self.client.get("/api/device/capabilities")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertEqual(root.status_code, 200)
        self.assertIn("New Era Glasses", root.text)
        self.assertEqual(capabilities.status_code, 200)
        self.assertEqual(capabilities.json()["adapter_name"], "browser_simulation")

    def test_user_session_endpoints_create_and_list_sessions(self) -> None:
        created = self.client.post(
            "/api/users/user_alpha/sessions",
            json={
                "module": "documents",
                "title": "Contract review session",
                "metadata": {"source": "smoke"},
            },
        )
        self.assertEqual(created.status_code, 200)
        session = created.json()
        self.assertEqual(session["user_id"], "user_alpha")
        self.assertEqual(session["module"], "documents")

        listed = self.client.get("/api/users/user_alpha/sessions")
        self.assertEqual(listed.status_code, 200)
        page = listed.json()
        self.assertEqual(page["session_count"], 1)
        self.assertEqual(page["sessions"][0]["session_id"], session["session_id"])

    def test_contract_review_persists_analysis_and_accepts_feedback(self) -> None:
        response = self.client.post(
            "/api/simulations/documents/contract-review",
            json={
                "user_id": "user_contract",
                "document_text": CONTRACT_TEXT,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["outcome"], "delivered")
        self.assertTrue(payload["candidate_created"])
        self.assertTrue(payload["analysis_id"])
        self.assertGreaterEqual(len(payload["analysis"]["findings"]), 2)

        session_id = payload["session_id"]
        analysis_id = payload["analysis_id"]
        command_id = payload["command"]["command_id"]

        analysis = self.client.get(f"/api/document-analyses/{analysis_id}")
        self.assertEqual(analysis.status_code, 200)
        self.assertEqual(analysis.json()["session_id"], session_id)

        analysis_list = self.client.get(f"/api/sessions/{session_id}/document-analyses")
        self.assertEqual(analysis_list.status_code, 200)
        self.assertEqual(analysis_list.json()[0]["analysis_id"], analysis_id)

        feedback = self.client.post(
            f"/api/lens/commands/{command_id}/feedback",
            json={
                "user_id": "user_contract",
                "session_id": session_id,
                "feedback": "useful",
            },
        )
        self.assertEqual(feedback.status_code, 200)
        self.assertEqual(feedback.json()["command_id"], command_id)

        trace = self.client.get(
            f"/api/sessions/{session_id}/trace",
            params={"step": "feedback"},
        )
        self.assertEqual(trace.status_code, 200)
        self.assertEqual(trace.json()["event_count"], 1)

    def test_document_job_flow_reaches_result_endpoint(self) -> None:
        response = self.client.post(
            "/api/jobs/documents/contract-analysis",
            json={
                "user_id": "user_jobs",
                "artifact_label": "membership-contract",
                "idempotency_key": "contract-job-0001",
                "document_text": CONTRACT_TEXT,
            },
        )
        self.assertEqual(response.status_code, 200)
        job = response.json()
        self.assertEqual(job["status"], "queued")

        final_job = self._wait_for_job(job["job_id"])
        self.assertEqual(final_job["status"], "succeeded")
        self.assertTrue(final_job["result_id"])

        result = self.client.get(f"/api/jobs/{job['job_id']}/result")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["analysis_id"], final_job["result_id"])

        trace = self.client.get(
            f"/api/sessions/{final_job['session_id']}/trace",
            params={"step": "job"},
        )
        self.assertEqual(trace.status_code, 200)
        self.assertGreaterEqual(trace.json()["event_count"], 2)

    def _wait_for_job(self, job_id: str, timeout_seconds: float = 3.0) -> dict[str, object]:
        deadline = time.monotonic() + timeout_seconds
        latest_payload: dict[str, object] | None = None
        while time.monotonic() < deadline:
            response = self.client.get(f"/api/jobs/{job_id}")
            self.assertEqual(response.status_code, 200)
            latest_payload = response.json()
            if latest_payload["status"] in {"succeeded", "failed"}:
                return latest_payload
            time.sleep(0.05)
        self.fail(f"job {job_id} did not finish in time; last payload={latest_payload}")
