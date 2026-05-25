from __future__ import annotations

from dataclasses import dataclass
from os import environ
from pathlib import Path

from new_era.application.ports.device_gateway import DeviceGateway
from new_era.application.ports.document_analysis_job_payload_store import (
    DocumentAnalysisJobPayloadStore,
)
from new_era.application.ports.document_analysis_store import DocumentAnalysisStore
from new_era.application.ports.event_store import EventStore
from new_era.application.ports.job_store import JobStore
from new_era.application.ports.observation_interpreter import ObservationInterpreter
from new_era.application.ports.session_store import SessionStore
from new_era.application.services.document_session import DocumentSessionService
from new_era.application.services.grocery_session import GrocerySessionService
from new_era.application.use_cases.deliver_lens_command import DeliverLensCommand
from new_era.application.use_cases.document_analysis_jobs import (
    AdvanceDocumentAnalysisJob,
    EnqueueDocumentAnalysisJob,
    GetJobStatus,
    RunDocumentAnalysisJob,
)
from new_era.application.use_cases.evaluate_alert_candidate import EvaluateAlertCandidate
from new_era.application.use_cases.get_document_analysis import (
    GetDocumentAnalysis,
    ListDocumentAnalysesBySession,
)
from new_era.application.use_cases.get_session_trace import GetSessionTrace
from new_era.application.use_cases.process_alert_candidate import ProcessAlertCandidate
from new_era.application.use_cases.process_observation import ProcessObservation
from new_era.application.use_cases.record_lens_feedback import RecordLensFeedback
from new_era.application.use_cases.user_sessions import (
    GetUserSession,
    ListUserSessions,
    StartUserSession,
)
from new_era.domain.attention.policy import AttentionPolicy
from new_era.domain.documents.analysis import DeterministicContractAnalyzer
from new_era.domain.jobs.models import JobExecutionPolicy
from new_era.infrastructure.device.browser_simulation_adapter import BrowserSimulationAdapter
from new_era.infrastructure.device.http_device_bridge_adapter import HttpDeviceBridgeAdapter
from new_era.infrastructure.documents.in_memory_document_analysis_store import (
    InMemoryDocumentAnalysisStore,
)
from new_era.infrastructure.events.in_memory_event_store import InMemoryEventStore
from new_era.infrastructure.events.sqlite_event_store import SQLiteEventStore
from new_era.infrastructure.jobs.in_memory_document_analysis_job_payload_store import (
    InMemoryDocumentAnalysisJobPayloadStore,
)
from new_era.infrastructure.jobs.in_memory_job_store import InMemoryJobStore
from new_era.infrastructure.jobs.threaded_document_analysis_job_worker import (
    ThreadedDocumentAnalysisJobWorker,
)
from new_era.infrastructure.observations.simple_simulation_adapter import (
    SimpleSimulationObservationAdapter,
)
from new_era.infrastructure.ocr.rapidocr_engine import RapidOCRAdapter
from new_era.infrastructure.sessions.in_memory_session_store import InMemorySessionStore
from new_era.infrastructure.sessions.sqlite_session_store import SQLiteSessionStore


@dataclass(frozen=True, slots=True)
class SimulationRuntime:
    grocery_service: GrocerySessionService
    document_service: DocumentSessionService
    session_trace_reader: GetSessionTrace
    document_job_enqueuer: EnqueueDocumentAnalysisJob
    document_job_advancer: AdvanceDocumentAnalysisJob
    job_status_reader: GetJobStatus
    document_analysis_reader: GetDocumentAnalysis
    document_analyses_by_session_reader: ListDocumentAnalysesBySession
    lens_feedback_recorder: RecordLensFeedback
    user_session_starter: StartUserSession
    user_session_reader: GetUserSession
    user_sessions_lister: ListUserSessions
    document_job_worker: ThreadedDocumentAnalysisJobWorker
    event_store: EventStore
    session_store: SessionStore
    job_store: JobStore
    document_job_payload_store: DocumentAnalysisJobPayloadStore
    document_analysis_store: DocumentAnalysisStore
    device_gateway: DeviceGateway

    @classmethod
    def build_default(
        cls,
        storage_path: str | Path | None = None,
        device_gateway: DeviceGateway | None = None,
    ) -> "SimulationRuntime":
        configured_storage_path = storage_path or environ.get("NEW_ERA_SQLITE_PATH")
        if configured_storage_path:
            event_store = SQLiteEventStore(configured_storage_path)
            session_store = SQLiteSessionStore(configured_storage_path)
        else:
            event_store = InMemoryEventStore()
            session_store = InMemorySessionStore()

        job_store = InMemoryJobStore()
        document_job_payload_store = InMemoryDocumentAnalysisJobPayloadStore()
        document_analysis_store = InMemoryDocumentAnalysisStore()
        device_gateway = device_gateway or build_device_gateway_from_environment()

        observation_interpreter: ObservationInterpreter = SimpleSimulationObservationAdapter()
        attention_policy = AttentionPolicy()
        contract_analyzer = DeterministicContractAnalyzer()
        ocr_engine = RapidOCRAdapter()
        job_execution_policy = JobExecutionPolicy(
            max_attempts=3,
            timeout_seconds=10.0,
            retry_backoff_seconds=0.0,
        )

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

        grocery_service = GrocerySessionService.build_simulation(
            observation_processor=observation_processor,
            event_store=event_store,
            device_gateway=device_gateway,
        )
        document_service = DocumentSessionService.build_simulation(
            observation_processor=observation_processor,
            event_store=event_store,
            device_gateway=device_gateway,
            contract_analyzer=contract_analyzer,
            ocr_engine=ocr_engine,
            analysis_store=document_analysis_store,
        )
        session_trace_reader = GetSessionTrace(event_store=event_store)
        document_job_enqueuer = EnqueueDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            payload_store=document_job_payload_store,
            execution_policy=job_execution_policy,
        )
        document_job_advancer = AdvanceDocumentAnalysisJob(
            job_store=job_store,
            event_store=event_store,
            document_analysis_store=document_analysis_store,
        )
        job_status_reader = GetJobStatus(job_store=job_store)
        document_analysis_reader = GetDocumentAnalysis(analysis_store=document_analysis_store)
        document_analyses_by_session_reader = ListDocumentAnalysesBySession(
            analysis_store=document_analysis_store,
        )
        lens_feedback_recorder = RecordLensFeedback(event_store=event_store)
        user_session_starter = StartUserSession(session_store=session_store)
        user_session_reader = GetUserSession(session_store=session_store)
        user_sessions_lister = ListUserSessions(session_store=session_store)
        document_job_worker = ThreadedDocumentAnalysisJobWorker(
            runner=RunDocumentAnalysisJob(
                job_store=job_store,
                event_store=event_store,
                payload_store=document_job_payload_store,
                document_processor=DocumentSessionService.build_simulation(
                    observation_processor=observation_processor,
                    event_store=event_store,
                    device_gateway=device_gateway,
                    contract_analyzer=contract_analyzer,
                    ocr_engine=ocr_engine,
                    analysis_store=document_analysis_store,
                ),
            ),
        )

        return cls(
            grocery_service=grocery_service,
            document_service=document_service,
            session_trace_reader=session_trace_reader,
            document_job_enqueuer=document_job_enqueuer,
            document_job_advancer=document_job_advancer,
            job_status_reader=job_status_reader,
            document_analysis_reader=document_analysis_reader,
            document_analyses_by_session_reader=document_analyses_by_session_reader,
            lens_feedback_recorder=lens_feedback_recorder,
            user_session_starter=user_session_starter,
            user_session_reader=user_session_reader,
            user_sessions_lister=user_sessions_lister,
            document_job_worker=document_job_worker,
            event_store=event_store,
            session_store=session_store,
            job_store=job_store,
            document_job_payload_store=document_job_payload_store,
            document_analysis_store=document_analysis_store,
            device_gateway=device_gateway,
        )


def build_device_gateway_from_environment() -> DeviceGateway:
    bridge_url = environ.get("NEW_ERA_DEVICE_BRIDGE_URL")
    if not bridge_url:
        return BrowserSimulationAdapter()

    timeout_seconds = 2.0
    timeout_value = environ.get("NEW_ERA_DEVICE_BRIDGE_TIMEOUT_SECONDS")
    if timeout_value:
        try:
            timeout_seconds = float(timeout_value)
        except ValueError:
            timeout_seconds = 2.0

    return HttpDeviceBridgeAdapter(
        bridge_url=bridge_url,
        api_token=environ.get("NEW_ERA_DEVICE_BRIDGE_TOKEN"),
        timeout_seconds=timeout_seconds,
    )
