from __future__ import annotations

from dataclasses import dataclass

from new_era.application.ports import (
    DeviceGateway,
    DocumentAnalysisJobPayloadStore,
    DocumentAnalysisStore,
    EventStore,
    JobStore,
    ObservationInterpreter,
)
from new_era.application.services.document_session import DocumentSessionService
from new_era.application.services.grocery_session import GrocerySessionService
from new_era.application.use_cases import (
    AdvanceDocumentAnalysisJob,
    DeliverLensCommand,
    EnqueueDocumentAnalysisJob,
    EvaluateAlertCandidate,
    GetDocumentAnalysis,
    GetJobStatus,
    GetSessionTrace,
    ListDocumentAnalysesBySession,
    ProcessAlertCandidate,
    ProcessObservation,
    RecordLensFeedback,
    RunDocumentAnalysisJob,
)
from new_era.domain.attention import AttentionPolicy
from new_era.domain.documents import DeterministicContractAnalyzer
from new_era.domain.jobs import JobExecutionPolicy
from new_era.infrastructure.device import BrowserSimulationAdapter
from new_era.infrastructure.documents import InMemoryDocumentAnalysisStore
from new_era.infrastructure.events import InMemoryEventStore
from new_era.infrastructure.jobs import (
    InMemoryDocumentAnalysisJobPayloadStore,
    InMemoryJobStore,
    ThreadedDocumentAnalysisJobWorker,
)
from new_era.infrastructure.observations import SimpleSimulationObservationAdapter
from new_era.infrastructure.ocr import RapidOCRAdapter


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
    document_job_worker: ThreadedDocumentAnalysisJobWorker
    event_store: EventStore
    job_store: JobStore
    document_job_payload_store: DocumentAnalysisJobPayloadStore
    document_analysis_store: DocumentAnalysisStore
    device_gateway: DeviceGateway

    @classmethod
    def build_default(cls) -> "SimulationRuntime":
        event_store = InMemoryEventStore()
        job_store = InMemoryJobStore()
        document_job_payload_store = InMemoryDocumentAnalysisJobPayloadStore()
        document_analysis_store = InMemoryDocumentAnalysisStore()
        device_gateway = BrowserSimulationAdapter()
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
                contract_analyzer=contract_analyzer,
                ocr_engine=ocr_engine,
                analysis_store=document_analysis_store,
            ),
            session_trace_reader=GetSessionTrace(event_store=event_store),
            document_job_enqueuer=EnqueueDocumentAnalysisJob(
                job_store=job_store,
                event_store=event_store,
                payload_store=document_job_payload_store,
                execution_policy=job_execution_policy,
            ),
            document_job_advancer=AdvanceDocumentAnalysisJob(
                job_store=job_store,
                event_store=event_store,
                document_analysis_store=document_analysis_store,
            ),
            job_status_reader=GetJobStatus(job_store=job_store),
            document_analysis_reader=GetDocumentAnalysis(
                analysis_store=document_analysis_store,
            ),
            document_analyses_by_session_reader=ListDocumentAnalysesBySession(
                analysis_store=document_analysis_store,
            ),
            lens_feedback_recorder=RecordLensFeedback(event_store=event_store),
            document_job_worker=ThreadedDocumentAnalysisJobWorker(
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
                )
            ),
            event_store=event_store,
            job_store=job_store,
            document_job_payload_store=document_job_payload_store,
            document_analysis_store=document_analysis_store,
            device_gateway=device_gateway,
        )
