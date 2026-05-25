import json
from unittest import TestCase

from fastapi.testclient import TestClient

from new_era.infrastructure.http.app import create_app


class PwaAssetTest(TestCase):
    def test_manifest_declares_restricted_install_scope(self) -> None:
        client = TestClient(create_app())

        response = client.get("/manifest.webmanifest")

        self.assertEqual(response.status_code, 200)
        manifest = json.loads(response.text)
        self.assertEqual(manifest["id"], "/")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["start_url"], "/")
        self.assertIn("Read-only offline shell", manifest["description"])
        self.assertFalse(manifest["prefer_related_applications"])

    def test_service_worker_limits_cache_to_shell_assets(self) -> None:
        client = TestClient(create_app())

        response = client.get("/service-worker.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn('const SHELL_CACHE_NAME = "new-era-shell-v3";', response.text)
        self.assertIn('const SENSITIVE_PATH_PREFIXES = [', response.text)
        self.assertIn('"/api/"', response.text)
        self.assertIn('"/uploads/"', response.text)
        self.assertIn('"/document-analyses/"', response.text)
        self.assertIn('"/jobs/"', response.text)
        self.assertIn('const SENSITIVE_RESPONSE_HEADERS = [', response.text)
        self.assertIn('cacheControl.includes("no-store")', response.text)
        self.assertIn('cacheControl.includes("private")', response.text)
        self.assertIn('response.headers.get("X-New-Era-Sensitive")', response.text)
        self.assertIn("function isSensitiveResponse(response)", response.text)
        self.assertIn('return cache.match(OFFLINE_SHELL_URL);', response.text)

    def test_index_exposes_job_policy_notice_region(self) -> None:
        client = TestClient(create_app())

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="job-policy-card"', response.text)
        self.assertIn('id="job-policy-message"', response.text)

    def test_app_js_prefers_policy_rejection_message(self) -> None:
        client = TestClient(create_app())

        response = client.get("/static/app.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("function isPolicyRejection(detail)", response.text)
        self.assertIn("return detail.message;", response.text)
        self.assertIn("payload.blocked_reason", response.text)
