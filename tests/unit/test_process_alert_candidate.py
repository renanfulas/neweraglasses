from dataclasses import dataclass
from unittest import TestCase

from new_era.application.ports import DeviceGateway
from new_era.application.use_cases import (
    AlertProcessingOutcome,
    DeliverLensCommand,
    EvaluateAlertCandidate,
    ProcessAlertCandidate,
)
from new_era.domain.attention import (
    AlertCandidate,
    AlertPriority,
    AttentionMode,
    AttentionPolicy,
)
from new_era.domain.device import DeviceCapabilities
from new_era.domain.events import EventType
from new_era.domain.lens import LensCommand
from new_era.infrastructure.device import BrowserSimulationAdapter
from new_era.infrastructure.events import InMemoryEventStore


def make_candidate(*, confidence: float = 0.9) -> AlertCandidate:
    return AlertCandidate(
        candidate_id="candidate_1",
        user_id="user_1",
        session_id="session_1",
        module="grocery",
        alert_type="missing_item",
        title="Missing item",
        body="You still need eggs.",
        priority=AlertPriority.MEDIUM,
        confidence=confidence,
        category="grocery",
    )


class ProcessAlertCandidateTest(TestCase):
    def test_evaluates_and_delivers_candidate(self) -> None:
        event_store = InMemoryEventStore()
        adapter = BrowserSimulationAdapter()
        processor = make_processor(event_store=event_store, device_gateway=adapter)

        result = processor.execute(
            candidate=make_candidate(),
            mode=AttentionMode.BALANCED,
            recent_category_count=0,
            correlation_id="corr_1",
            trace_id="trace_1",
        )

        self.assertEqual(result.outcome, AlertProcessingOutcome.DELIVERED)
        self.assertIsNotNone(result.command)
        self.assertEqual(adapter.delivered_commands, [result.command])
        self.assertEqual(
            [event.event_type for event in event_store.events],
            [
                EventType.ALERT_CANDIDATE_CREATED,
                EventType.ALERT_SHOWN,
                EventType.LENS_COMMAND_DELIVERED,
            ],
        )

    def test_suppresses_candidate_before_delivery(self) -> None:
        event_store = InMemoryEventStore()
        adapter = BrowserSimulationAdapter()
        processor = make_processor(event_store=event_store, device_gateway=adapter)

        result = processor.execute(
            candidate=make_candidate(confidence=0.2),
            mode=AttentionMode.BALANCED,
            recent_category_count=0,
            correlation_id="corr_1",
            trace_id="trace_1",
        )

        self.assertEqual(result.outcome, AlertProcessingOutcome.SUPPRESSED)
        self.assertIsNone(result.command)
        self.assertEqual(adapter.delivered_commands, [])
        self.assertEqual(
            [event.event_type for event in event_store.events],
            [EventType.ALERT_CANDIDATE_CREATED, EventType.ALERT_SUPPRESSED],
        )

    def test_skips_delivery_when_device_lacks_display(self) -> None:
        event_store = InMemoryEventStore()
        adapter = NoDisplayAdapter()
        processor = make_processor(event_store=event_store, device_gateway=adapter)

        result = processor.execute(
            candidate=make_candidate(),
            mode=AttentionMode.BALANCED,
            recent_category_count=0,
            correlation_id="corr_1",
            trace_id="trace_1",
        )

        self.assertEqual(result.outcome, AlertProcessingOutcome.DELIVERY_SKIPPED)
        self.assertIsNotNone(result.command)
        self.assertEqual(adapter.delivered_commands, [])
        self.assertEqual(event_store.events[-1].event_type, EventType.DEVICE_CAPABILITY_MISSING)


def make_processor(
    *,
    event_store: InMemoryEventStore,
    device_gateway: DeviceGateway,
) -> ProcessAlertCandidate:
    return ProcessAlertCandidate(
        evaluator=EvaluateAlertCandidate(
            attention_policy=AttentionPolicy(),
            event_store=event_store,
        ),
        delivery=DeliverLensCommand(
            device_gateway=device_gateway,
            event_store=event_store,
        ),
    )


@dataclass(slots=True)
class NoDisplayAdapter(DeviceGateway):
    delivered_commands: list[LensCommand]

    def __init__(self) -> None:
        self.delivered_commands = []

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
