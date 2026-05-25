from __future__ import annotations

from dataclasses import dataclass, field
from unittest import TestCase

from new_era.application.ports import DeviceDeliveryError, DeviceGateway
from new_era.application.use_cases import DeliverLensCommand
from new_era.domain.attention import AlertPriority
from new_era.domain.device import DeviceCapabilities
from new_era.domain.events import EventType
from new_era.domain.lens import LensCommand, LensCommandType
from new_era.infrastructure.device import BrowserSimulationAdapter
from new_era.infrastructure.events import InMemoryEventStore


def make_command() -> LensCommand:
    return LensCommand(
        command_id="cmd_1",
        command_version=1,
        command_type=LensCommandType.SHOW_ALERT,
        priority=AlertPriority.MEDIUM,
        title="Missing item",
        body="You still need eggs.",
        duration_ms=5000,
    )


class DeliverLensCommandTest(TestCase):
    def test_delivers_command_to_device_and_records_event(self) -> None:
        event_store = InMemoryEventStore()
        adapter = BrowserSimulationAdapter()
        use_case = DeliverLensCommand(device_gateway=adapter, event_store=event_store)
        command = make_command()

        delivered = use_case.execute(
            command=command,
            user_id="user_1",
            session_id="session_1",
            module="grocery",
            correlation_id="corr_1",
            trace_id="trace_1",
        )

        self.assertTrue(delivered)
        self.assertEqual(adapter.delivered_commands, [command])
        self.assertEqual(event_store.events[-1].event_type, EventType.LENS_COMMAND_DELIVERED)
        self.assertEqual(
            event_store.events[-1].metadata["adapter_name"],
            "browser_simulation",
        )

    def test_records_capability_missing_when_display_is_unsupported(self) -> None:
        event_store = InMemoryEventStore()
        adapter = NoDisplayAdapter()
        use_case = DeliverLensCommand(device_gateway=adapter, event_store=event_store)

        delivered = use_case.execute(
            command=make_command(),
            user_id="user_1",
            session_id="session_1",
            module="grocery",
            correlation_id="corr_1",
            trace_id="trace_1",
        )

        self.assertFalse(delivered)
        self.assertEqual(adapter.delivered_commands, [])
        self.assertEqual(
            event_store.events[-1].event_type,
            EventType.DEVICE_CAPABILITY_MISSING,
        )
        self.assertEqual(event_store.events[-1].metadata["missing_capability"], "display")

    def test_records_delivery_failure_when_bridge_rejects_command(self) -> None:
        event_store = InMemoryEventStore()
        adapter = FailingDeliveryAdapter()
        use_case = DeliverLensCommand(device_gateway=adapter, event_store=event_store)

        delivered = use_case.execute(
            command=make_command(),
            user_id="user_1",
            session_id="session_1",
            module="grocery",
            correlation_id="corr_1",
            trace_id="trace_1",
        )

        self.assertFalse(delivered)
        self.assertEqual(
            event_store.events[-1].event_type,
            EventType.DEVICE_DELIVERY_FAILED,
        )
        self.assertEqual(event_store.events[-1].metadata["adapter_name"], "failing_bridge")


@dataclass(slots=True)
class NoDisplayAdapter(DeviceGateway):
    delivered_commands: list[LensCommand] = field(default_factory=list)

    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(
            adapter_name="no_display",
            supports_camera=True,
            supports_display=False,
            supports_voice=False,
            supports_gesture=False,
        )

    def deliver(self, command: LensCommand) -> None:
        self.delivered_commands.append(command)


@dataclass(slots=True)
class FailingDeliveryAdapter(DeviceGateway):
    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(
            adapter_name="failing_bridge",
            supports_camera=True,
            supports_display=True,
            supports_voice=False,
            supports_gesture=False,
        )

    def deliver(self, command: LensCommand) -> None:
        raise DeviceDeliveryError("bridge unavailable")
