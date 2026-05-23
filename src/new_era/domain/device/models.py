from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class DeviceCapabilities:
    adapter_name: str
    supports_camera: bool
    supports_display: bool
    supports_voice: bool
    supports_gesture: bool
    unsupported_features: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
