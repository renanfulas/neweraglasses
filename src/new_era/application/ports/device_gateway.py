from __future__ import annotations

from typing import Protocol

from new_era.domain.device import DeviceCapabilities
from new_era.domain.lens import LensCommand


class DeviceGatewayError(RuntimeError):
    pass


class DeviceDeliveryError(DeviceGatewayError):
    pass


class DeviceGateway(Protocol):
    def capabilities(self) -> DeviceCapabilities:
        raise NotImplementedError

    def deliver(self, command: LensCommand) -> None:
        raise NotImplementedError
