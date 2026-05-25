from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class DeviceCapabilities:
    adapter_name: str
    supports_camera: bool = False
    supports_display: bool = True
    supports_voice: bool = False
    supports_gesture: bool = False
    unsupported_features: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)


class DeviceGatewayError(RuntimeError):
    """Raised when a device adapter cannot deliver a lens command."""


class DeviceDeliveryError(DeviceGatewayError):
    """Raised when delivery to a device bridge fails."""


class DeviceGateway(Protocol):
    def capabilities(self) -> DeviceCapabilities:
        raise NotImplementedError

    def get_capabilities(self) -> DeviceCapabilities:
        raise NotImplementedError

    def deliver(self, command: object) -> bool:
        raise NotImplementedError
