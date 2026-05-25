from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from new_era.application.ports import DeviceDeliveryError, DeviceGateway, DeviceGatewayError
from new_era.domain.device import DeviceCapabilities
from new_era.domain.lens import LensCommand


@dataclass(slots=True)
class HttpDeviceBridgeAdapter(DeviceGateway):
    bridge_url: str
    api_token: str | None = None
    timeout_seconds: float = 2.0
    adapter_name: str = "http_device_bridge"
    capabilities_path: str = "/capabilities"
    lens_commands_path: str = "/lens-commands"

    def __post_init__(self) -> None:
        self.bridge_url = self.bridge_url.rstrip("/")
        if not self.bridge_url:
            raise ValueError("bridge_url is required")

    def capabilities(self) -> DeviceCapabilities:
        try:
            payload = self._request_json("GET", self.capabilities_path)
        except DeviceGatewayError as exc:
            return DeviceCapabilities(
                adapter_name=self.adapter_name,
                supports_camera=True,
                supports_display=True,
                supports_voice=False,
                supports_gesture=False,
                unsupported_features=("capability_probe_unavailable",),
                metadata={
                    "bridge_url": self.bridge_url,
                    "capability_error": exc.__class__.__name__,
                },
            )

        return DeviceCapabilities(
            adapter_name=str(payload.get("adapter_name", self.adapter_name)),
            supports_camera=bool(payload.get("supports_camera", True)),
            supports_display=bool(payload.get("supports_display", True)),
            supports_voice=bool(payload.get("supports_voice", False)),
            supports_gesture=bool(payload.get("supports_gesture", False)),
            unsupported_features=tuple(
                str(feature) for feature in payload.get("unsupported_features", [])
            ),
            metadata={
                **self._safe_metadata(payload.get("metadata")),
                "bridge_url": self.bridge_url,
            },
        )

    def deliver(self, command: LensCommand) -> None:
        try:
            self._request_json(
                "POST",
                self.lens_commands_path,
                payload={"command": command.to_dict()},
            )
        except DeviceGatewayError as exc:
            raise DeviceDeliveryError("device bridge delivery failed") from exc

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "new-era-glasses/0.1",
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        request = Request(
            urljoin(f"{self.bridge_url}/", path.lstrip("/")),
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_body = response.read()
        except HTTPError as exc:
            raise DeviceGatewayError(f"bridge returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise DeviceGatewayError("bridge unavailable") from exc
        except TimeoutError as exc:
            raise DeviceGatewayError("bridge timed out") from exc
        except OSError as exc:
            raise DeviceGatewayError("bridge unavailable") from exc

        if not response_body:
            return {}
        try:
            decoded = json.loads(response_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise DeviceGatewayError("bridge returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise DeviceGatewayError("bridge returned a non-object JSON payload")
        return decoded

    def _safe_metadata(self, value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            return {}
        forbidden_keys = {"access_token", "api_key", "authorization", "secret", "token"}
        return {
            str(key): metadata_value
            for key, metadata_value in value.items()
            if str(key).lower() not in forbidden_keys
        }
