from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from new_era.application.ports import DeviceDeliveryError
from new_era.domain.attention import AlertPriority
from new_era.domain.lens import LensCommand, LensCommandType
from new_era.infrastructure.device import HttpDeviceBridgeAdapter


class BridgeHarnessHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/capabilities":
            self.send_response(404)
            self.end_headers()
            return

        payload = {
            "adapter_name": "local_harness_bridge",
            "supports_camera": True,
            "supports_display": True,
            "supports_voice": False,
            "supports_gesture": True,
            "unsupported_features": ["native_pairing"],
            "metadata": {
                "hardware": "local_http_harness",
                "token": "redacted-by-adapter",
            },
        }
        self._write_json(200, payload)

    def do_POST(self) -> None:
        if self.path == "/slow-lens-commands":
            time.sleep(0.35)
            self._write_json(202, {"accepted": True, "mode": "slow"})
            return
        if self.path != "/lens-commands":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.received_payloads.append(json.loads(body.decode("utf-8")))  # type: ignore[attr-defined]
        self.server.received_authorization = self.headers.get("Authorization")  # type: ignore[attr-defined]
        self._write_json(202, {"accepted": True})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _write_json(self, status_code: int, payload: dict[str, object]) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        try:
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        except (BrokenPipeError, ConnectionAbortedError):
            return


def make_demo_command() -> LensCommand:
    return LensCommand(
        command_id="cmd_bridge_harness",
        command_version=1,
        command_type=LensCommandType.SHOW_ALERT,
        priority=AlertPriority.HIGH,
        title="Contract clause needs attention",
        body="Check the automatic renewal clause before signing.",
        duration_ms=7000,
    )


def run_harness() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), BridgeHarnessHandler)
    server.received_payloads = []  # type: ignore[attr-defined]
    server.received_authorization = None  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    bridge_url = f"http://127.0.0.1:{server.server_port}"

    try:
        adapter = HttpDeviceBridgeAdapter(
            bridge_url=bridge_url,
            api_token="local-bridge-token",
            timeout_seconds=1.0,
        )
        capabilities = adapter.capabilities()
        if capabilities.adapter_name != "local_harness_bridge":
            raise RuntimeError("capability probe returned the wrong adapter name")
        if not capabilities.supports_camera or not capabilities.supports_display:
            raise RuntimeError("capability probe did not report camera and display support")
        if "token" in capabilities.metadata:
            raise RuntimeError("capability metadata leaked a sensitive token")

        adapter.deliver(make_demo_command())
        if server.received_authorization != "Bearer local-bridge-token":  # type: ignore[attr-defined]
            raise RuntimeError("bridge delivery did not include the configured bearer token")
        if len(server.received_payloads) != 1:  # type: ignore[attr-defined]
            raise RuntimeError("bridge did not receive exactly one lens command")

        failing_adapter = HttpDeviceBridgeAdapter(
            bridge_url=f"{bridge_url}/missing",
            timeout_seconds=0.2,
        )
        try:
            failing_adapter.deliver(make_demo_command())
        except DeviceDeliveryError:
            pass
        else:
            raise RuntimeError("bridge delivery failure was not surfaced")

        timeout_adapter = HttpDeviceBridgeAdapter(
            bridge_url=bridge_url,
            timeout_seconds=0.1,
            lens_commands_path="/slow-lens-commands",
        )
        try:
            timeout_adapter.deliver(make_demo_command())
        except DeviceDeliveryError:
            pass
        else:
            raise RuntimeError("bridge timeout was not surfaced")

        print("[bridge] capabilities: ok")
        print("[bridge] delivery: ok")
        print("[bridge] failure path: ok")
        print("[bridge] timeout path: ok")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def main() -> int:
    run_harness()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
