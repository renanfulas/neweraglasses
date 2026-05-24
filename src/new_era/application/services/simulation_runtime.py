from __future__ import annotations

from dataclasses import dataclass

from new_era.application.ports import DeviceGateway, EventStore, JobStore, ObservationInterpreter
from new_era.application.services.document_session import DocumentSessionService
from new_era.application.services.grocery_session import GrocerySessionService
from new_era.application.use_cases import (
    AdvanceDocumentAnalysisJob,
    DeliverLensCommand,
    EnqueueDocumentAnalysisJob,
    EvaluateAlertCandidate,
    GetJobStatus,
    GetSessionTrace,
    ProcessAlertCandidate,
    ProcessObservation,
)
from new_era.domain.attention import AttentionPolicy
from new_era.infrastructure.device import BrowserSimulationAdapter
from new_era.infrastructure.events import InMemoryEventStore
from new_era.infrastructure.jobs import InMemoryJobStore
from new_era.infrastructure.observations import SimpleSimulationObservationAdapter


@dataclass(frozen=True, slots=True)
class SimulationRuntime:
    grocery_service: GrocerySessionService
    document_service: DocumentSessionService
    session_trace_reader: GetSessionTrace
    document_job_enqueuer: EnqueueDocumentAnalysisJob
    document_job_advancer: AdvanceDocumentAnalysisJob
    job_status_reader: GetJobStatus
    event_store: EventStore
    job_store: JobStore
    device_gateway: DeviceGateway

    @classmethod
    def build_default(cls) -> "SimulationRuntime":
        event_store = InMemoryEventStore()
        job_store = InMemoryJobStore()
        device_gateway = BrowserSimulationAdapter()
        observation_interpreter: ObservationInterpreter = SimpleSimulationObservationAdapter()
        attention_policy = AttentionPolicy()

        observation_processor = ProcessObservation(
            observation_interpreter=observation_interpreter,
            alert_processor=ProcessAlertCandidate(
                evaluator=EvaluateAlertCandidate(
                    attention_policy=attention_policy,
                    event_store=event_store,
                ),
                delivery=DeliverLensCommand(
                    device_gateway=device_gateway,
                    event_store=event_store,
                ),
            ),
            event_store=event_store,
        )

        return cls(
            grocery_service=GrocerySessionService.build_simulation(
                observation_processor=observation_processor,
                event_store=event_store,
                device_gateway=device_gateway,
            ),
            document_service=DocumentSessionService.build_simulation(
                observation_processor=observation_processor,
                event_store=event_store,
                device_gateway=device_gateway,
            ),
            session_trace_reader=GetSessionTrace(event_store=event_store),
            document_job_enqueuer=EnqueueDocumentAnalysisJob(
                job_store=job_store,
                event_store=event_store,
            ),
            document_job_advancer=AdvanceDocumentAnalysisJob(
                job_store=job_store,
                event_store=event_store,
            ),
            job_status_reader=GetJobStatus(job_store=job_store),
            event_store=event_store,
            job_store=job_store,
            device_gateway=device_gateway,
        )
