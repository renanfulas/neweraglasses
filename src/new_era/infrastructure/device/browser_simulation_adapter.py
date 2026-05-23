from __future__ import annotations

from dataclasses import dataclass, field

from new_era.application.ports import DeviceGateway
from new_era.domain.device import DeviceCapabilities
from new_era.domain.lens import LensCommand


@dataclass(slots=True)
class BrowserSimulationAdapter(DeviceGateway):
    delivered_commands: list[LensCommand] = field(default_factory=list)

    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(
            adapter_name="browser_simulation",
            supports_camera=True,
            supports_display=True,
            supports_voice=False,
            supports_gesture=False,
            unsupported_features=("native_background_bridge", "hardware_lens_display"),
        )

    def deliver(self, command: LensCommand) -> None:
        self.delivered_commands.append(command)
