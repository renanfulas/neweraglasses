from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import TestCase

from new_era.application.ports import DeviceDeliveryError
from new_era.domain.attention import AlertPriority
from new_era.domain.lens import LensCommand, LensCommandType
from new_era.infrastructure.device import HttpDeviceBridgeAdapter


def make_command() -> LensCommand:
    return LensCommand(
        command_id="cmd_bridge_1",
        command_version=1,
        command_type=LensCommandType.SHOW_ALERT,
        priority=AlertPriority.HIGH,
        title="Contract clause needs attention",
        body="Check the automatic renewal clause.",
        duration_ms=7000,
    )


class BridgeRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/capabilities":
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(self.server.capabilities_payload).encode("utf-8"))

    def do_POST(self) -> None:
        if self.path != "/lens-commands":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.received_payloads.append(json.loads(body.decode("utf-8")))
        self.server.received_authorization = self.headers.get("Authorization")
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"accepted": true}')

    def log_message(self, format: str, *args) -> None:
        return


class HttpDeviceBridgeAdapterTest(TestCase):
    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), BridgeRequestHandler)
        self.server.capabilities_payload = {
            "adapter_name": "phone_native_bridge",
            "supports_camera": True,
            "supports_display": True,
            "supports_voice": False,
            "supports_gesture": True,
            "unsupported_features": ["always_on_recording"],
            "metadata": {
                "hardware": "phone_camera",
                "token": "must_not_leak",
            },
        }
        self.server.received_payloads = []
        self.server.received_authorization = None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.bridge_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_reads_capabilities_from_real_http_bridge(self) -> None:
        adapter = HttpDeviceBridgeAdapter(bridge_url=self.bridge_url)

        capabilities = adapter.capabilities()

        self.assertEqual(capabilities.adapter_name, "phone_native_bridge")
        self.assertTrue(capabilities.supports_camera)
        self.assertTrue(capabilities.supports_display)
        self.assertTrue(capabilities.supports_gesture)
        self.assertEqual(capabilities.unsupported_features, ("always_on_recording",))
        self.assertEqual(capabilities.metadata["hardware"], "phone_camera")
        self.assertNotIn("token", capabilities.metadata)

    def test_posts_lens_command_to_real_http_bridge(self) -> None:
        adapter = HttpDeviceBridgeAdapter(
            bridge_url=self.bridge_url,
            api_token="bridge-token",
        )

        adapter.deliver(make_command())

        self.assertEqual(self.server.received_authorization, "Bearer bridge-token")
        self.assertEqual(len(self.server.received_payloads), 1)
        payload = self.server.received_payloads[0]
        self.assertEqual(payload["command"]["command_id"], "cmd_bridge_1")
        self.assertEqual(payload["command"]["command_type"], "show_alert")
        self.assertEqual(payload["command"]["title"], "Contract clause needs attention")

    def test_delivery_failure_is_reported_as_device_delivery_error(self) -> None:
        adapter = HttpDeviceBridgeAdapter(
            bridge_url=f"{self.bridge_url}/missing",
            timeout_seconds=0.2,
        )

        with self.assertRaises(DeviceDeliveryError):
            adapter.deliver(make_command())
