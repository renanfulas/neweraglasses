from unittest import TestCase

from new_era.domain.attention import AlertPriority
from new_era.domain.lens import LensCommand, LensCommandType
from new_era.infrastructure.device import BrowserSimulationAdapter


class BrowserSimulationAdapterTest(TestCase):
    def test_exposes_browser_simulation_capabilities(self) -> None:
        adapter = BrowserSimulationAdapter()

        capabilities = adapter.capabilities()

        self.assertEqual(capabilities.adapter_name, "browser_simulation")
        self.assertTrue(capabilities.supports_camera)
        self.assertTrue(capabilities.supports_display)
        self.assertFalse(capabilities.supports_voice)

    def test_stores_delivered_lens_commands(self) -> None:
        adapter = BrowserSimulationAdapter()
        command = LensCommand(
            command_id="cmd_1",
            command_version=1,
            command_type=LensCommandType.SHOW_ALERT,
            priority=AlertPriority.MEDIUM,
            title="Missing item",
            body="You still need eggs.",
            duration_ms=5000,
        )

        adapter.deliver(command)

        self.assertEqual(adapter.delivered_commands, [command])
