"""Device infrastructure adapters."""

from new_era.infrastructure.device.browser_simulation_adapter import (
    BrowserSimulationAdapter,
)
from new_era.infrastructure.device.http_device_bridge_adapter import HttpDeviceBridgeAdapter

__all__ = ["BrowserSimulationAdapter", "HttpDeviceBridgeAdapter"]
