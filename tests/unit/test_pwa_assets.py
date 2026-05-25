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
        self.assertFalse(manifest["prefer_related_applications"])

    def test_service_worker_limits_cache_to_shell_assets(self) -> None:
        client = TestClient(create_app())

        response = client.get("/service-worker.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn('const SHELL_CACHE_NAME = "new-era-shell-v2";', response.text)
        self.assertIn('const NO_FALLBACK_PREFIXES = [', response.text)
        self.assertIn('"/api/"', response.text)
        self.assertIn('"/uploads/"', response.text)
        self.assertIn('"/document-analyses/"', response.text)
        self.assertIn('"/jobs/"', response.text)
        self.assertIn('return cache.match(OFFLINE_SHELL_URL);', response.text)
