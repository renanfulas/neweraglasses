from __future__ import annotations

from dataclasses import dataclass

from new_era.application.ports import DeviceGateway, DeviceGatewayError, EventStore
from new_era.domain.events import Event, EventType
from new_era.domain.lens import LensCommand


@dataclass(frozen=True, slots=True)
class DeliverLensCommand:
    device_gateway: DeviceGateway
    event_store: EventStore

    def execute(
        self,
        command: LensCommand,
        user_id: str,
        session_id: str,
        module: str,
        correlation_id: str,
        trace_id: str,
    ) -> bool:
        capabilities = self.device_gateway.capabilities()

        if not capabilities.supports_display:
            self.event_store.append(
                Event(
                    event_type=EventType.DEVICE_CAPABILITY_MISSING,
                    user_id=user_id,
                    session_id=session_id,
                    module=module,
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    metadata={
                        "adapter_name": capabilities.adapter_name,
                        "missing_capability": "display",
                        "command_id": command.command_id,
                    },
                )
            )
            return False

        try:
            self.device_gateway.deliver(command)
        except DeviceGatewayError as exc:
            self.event_store.append(
                Event(
                    event_type=EventType.DEVICE_DELIVERY_FAILED,
                    user_id=user_id,
                    session_id=session_id,
                    module=module,
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    metadata={
                        "adapter_name": capabilities.adapter_name,
                        "command_id": command.command_id,
                        "error_type": exc.__class__.__name__,
                    },
                )
            )
            return False

        self.event_store.append(
            Event(
                event_type=EventType.LENS_COMMAND_DELIVERED,
                user_id=user_id,
                session_id=session_id,
                module=module,
                correlation_id=correlation_id,
                trace_id=trace_id,
                metadata={
                    "adapter_name": capabilities.adapter_name,
                    "command_id": command.command_id,
                    "command_type": command.command_type.value,
                },
            )
        )
        return True
