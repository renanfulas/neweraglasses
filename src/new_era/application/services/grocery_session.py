from __future__ import annotations

from dataclasses import dataclass

from new_era.application.ports import DeviceGateway, EventStore, ObservationInterpreter
from new_era.application.use_cases import ProcessObservation
from new_era.domain.attention import AttentionMode
from new_era.domain.observations import Observation, ObservationKind
from new_era.infrastructure.device import BrowserSimulationAdapter
from new_era.infrastructure.events import InMemoryEventStore
from new_era.infrastructure.observations import SimpleSimulationObservationAdapter


@dataclass(frozen=True, slots=True)
class GrocerySessionService:
    observation_processor: ProcessObservation
    event_store: EventStore
    device_gateway: DeviceGateway

    def process_missing_item(
        self,
        *,
        observation_id: str,
        user_id: str,
        session_id: str,
        item_name: str,
        confidence: float,
        mode: AttentionMode,
        recent_category_count: int,
        correlation_id: str,
        trace_id: str,
    ):
        observation = Observation(
            observation_id=observation_id,
            user_id=user_id,
            session_id=session_id,
            module="grocery",
            kind=ObservationKind.GROCERY_MISSING_ITEM,
            summary=f"Missing {item_name} in grocery session",
            metadata={"item_name": item_name, "confidence": confidence},
        )
        return self.observation_processor.execute(
            observation=observation,
            mode=mode,
            recent_category_count=recent_category_count,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )

    @classmethod
    def build_simulation(
        cls,
        *,
        observation_processor: ProcessObservation,
        event_store: EventStore,
        device_gateway: DeviceGateway,
    ) -> "GrocerySessionService":
        return cls(
            observation_processor=observation_processor,
            event_store=event_store,
            device_gateway=device_gateway,
        )

    @classmethod
    def build_default_simulation(cls) -> "GrocerySessionService":
        from new_era.application.use_cases import (
            DeliverLensCommand,
            EvaluateAlertCandidate,
            ProcessAlertCandidate,
        )
        from new_era.domain.attention import AttentionPolicy

        event_store = InMemoryEventStore()
        device_gateway = BrowserSimulationAdapter()
        observation_interpreter: ObservationInterpreter = SimpleSimulationObservationAdapter()
        observation_processor = ProcessObservation(
            observation_interpreter=observation_interpreter,
            alert_processor=ProcessAlertCandidate(
                evaluator=EvaluateAlertCandidate(
                    attention_policy=AttentionPolicy(),
                    event_store=event_store,
                ),
                delivery=DeliverLensCommand(
                    device_gateway=device_gateway,
                    event_store=event_store,
                ),
            ),
            event_store=event_store,
        )
        return cls.build_simulation(
            observation_processor=observation_processor,
            event_store=event_store,
            device_gateway=device_gateway,
        )
