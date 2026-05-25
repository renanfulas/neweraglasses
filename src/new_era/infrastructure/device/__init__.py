"""Device infrastructure adapters."""

from .browser_simulation_adapter import BrowserSimulationAdapter
from .http_device_bridge_adapter import HttpDeviceBridgeAdapter

__all__ = ["BrowserSimulationAdapter", "HttpDeviceBridgeAdapter"]
