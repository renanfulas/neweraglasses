from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from new_era.application.services import (
    DocumentSessionService,
    GrocerySessionService,
    SimulationRuntime,
)
from new_era.application.use_cases import AdvanceDocumentAnalysisJob, GetJobStatus, GetSessionTrace
from new_era.application.use_cases import GetDocumentAnalysis, ListDocumentAnalysesBySession
from new_era.application.use_cases import LensFeedbackValue, RecordLensFeedback
from new_era.domain.documents import DocumentAnalysisRecord
from new_era.domain.attention import AttentionMode
from new_era.domain.jobs import JobRecord, JobStatus


class HealthResponse(BaseModel):
    status: str


class GroceryMissingItemRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_id: str
    session_id: str
    item_name: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1, default=0.9)
    mode: AttentionMode = AttentionMode.BALANCED
    recent_category_count: int = Field(ge=0, default=0)
    observation_id: str | None = None
    correlation_id: str | None = None
    trace_id: str | None = None


class DocumentContractReviewRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_id: str
    session_id: str
    document_text: str | None = Field(default=None, min_length=20)
    document_image_base64: str | None = None
    confidence: float | None = Field(default=0.92, ge=0, le=1)
    mode: AttentionMode = AttentionMode.BALANCED
    recent_category_count: int = Field(ge=0, default=0)
    observation_id: str | None = None
    correlation_id: str | None = None
    trace_id: str | None = None


class SimulationResponse(BaseModel):
    outcome: str
    candidate_created: bool
    command: dict[str, object] | None
    event_count: int
    delivered_commands_count: int
    session_trace: list[dict[str, object]]
    analysis: dict[str, object] | None = None
    analysis_id: str | None = None


class SessionTraceResponse(BaseModel):
    session_id: str
    trace_id: str | None
    event_count: int
    session_trace: list[dict[str, object]]


class DocumentAnalysisJobRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_id: str
    session_id: str
    artifact_label: str = Field(min_length=1)
    source_type: str = Field(min_length=1, default="pwa_simulation")
    idempotency_key: str = Field(min_length=8)
    document_text: str | None = Field(default=None, min_length=20)
    document_image_base64: str | None = None
    confidence: float | None = Field(default=0.92, ge=0, le=1)
    mode: AttentionMode = AttentionMode.BALANCED
    recent_category_count: int = Field(ge=0, default=0)
    observation_id: str | None = None
    correlation_id: str | None = None
    trace_id: str | None = None


class JobResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    user_id: str
    session_id: str
    module: str
    idempotency_key: str
    attempts: int
    max_attempts: int
    timeout_seconds: float
    retry_backoff_seconds: float
    result_id: str | None
    error_code: str | None
    error_message: str | None
    created_at: str
    updated_at: str
    started_at: str | None
    completed_at: str | None
    metadata: dict[str, object]


class JobTransitionRequest(BaseModel):
    target_status: JobStatus
    analysis_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    correlation_id: str | None = None
    trace_id: str | None = None


class LensFeedbackRequest(BaseModel):
    user_id: str
    session_id: str
    feedback: LensFeedbackValue
    correlation_id: str | None = None
    trace_id: str | None = None


class LensFeedbackResponse(BaseModel):
    event_id: str
    command_id: str
    feedback: str


class DocumentAnalysisResponse(BaseModel):
    analysis_id: str
    user_id: str
    session_id: str
    observation_id: str
    trace_id: str
    source_type: str
    created_at: str
    analysis: dict[str, object]


def serialize_job(job: JobRecord) -> JobResponse:
    return JobResponse(**job.to_dict())


def serialize_document_analysis(record: DocumentAnalysisRecord) -> DocumentAnalysisResponse:
    return DocumentAnalysisResponse(**record.to_dict())


def get_runtime(request: Request) -> SimulationRuntime:
    return request.app.state.runtime


def get_grocery_session_service(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> GrocerySessionService:
    return runtime.grocery_service


def get_document_session_service(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> DocumentSessionService:
    return runtime.document_service


def get_session_trace_reader(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> GetSessionTrace:
    return runtime.session_trace_reader


def get_document_job_enqueuer(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
):
    return runtime.document_job_enqueuer


def get_job_status_reader(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> GetJobStatus:
    return runtime.job_status_reader


def get_document_job_advancer(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> AdvanceDocumentAnalysisJob:
    return runtime.document_job_advancer


def get_document_job_worker(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
):
    return runtime.document_job_worker


def get_document_analysis_reader(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> GetDocumentAnalysis:
    return runtime.document_analysis_reader


def get_document_analyses_by_session_reader(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> ListDocumentAnalysesBySession:
    return runtime.document_analyses_by_session_reader


def get_lens_feedback_recorder(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> RecordLensFeedback:
    return runtime.lens_feedback_recorder


def build_simulation_response(
    *,
    result,
    session_trace_reader: GetSessionTrace,
    session_id: str,
    delivered_commands: list[object],
    trace_id: str,
    analysis: dict[str, object] | None = None,
    analysis_id: str | None = None,
) -> SimulationResponse:
    session_trace = session_trace_reader.execute(session_id=session_id, trace_id=trace_id)
    return SimulationResponse(
        outcome=result.outcome.value,
        candidate_created=result.candidate_created,
        command=result.alert_result.command.to_dict()
        if result.alert_result and result.alert_result.command
        else None,
        event_count=session_trace.event_count,
        delivered_commands_count=len(delivered_commands),
        session_trace=[entry.to_dict() for entry in session_trace.session_trace],
        analysis=analysis,
        analysis_id=analysis_id,
    )


def create_app() -> FastAPI:
    runtime = SimulationRuntime.build_default()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.runtime.document_job_worker.stop()

    app = FastAPI(title="New Era Glasses API", version="0.1.0", lifespan=lifespan)
    static_dir = Path(__file__).with_name("static")
    app.state.runtime = runtime

    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/manifest.webmanifest")
    def manifest() -> FileResponse:
        return FileResponse(static_dir / "manifest.webmanifest")

    @app.get("/service-worker.js")
    def service_worker() -> FileResponse:
        return FileResponse(static_dir / "service-worker.js")

    @app.post(
        "/api/simulations/grocery/missing-item",
        response_model=SimulationResponse,
    )
    def simulate_grocery_missing_item(
        request: GroceryMissingItemRequest,
        service: Annotated[GrocerySessionService, Depends(get_grocery_session_service)],
        session_trace_reader: Annotated[GetSessionTrace, Depends(get_session_trace_reader)],
    ) -> SimulationResponse:
        trace_id = request.trace_id or f"trace_{uuid4().hex}"
        result = service.process_missing_item(
            observation_id=request.observation_id or f"obs_{uuid4().hex}",
            user_id=request.user_id,
            session_id=request.session_id,
            item_name=request.item_name,
            confidence=request.confidence,
            mode=request.mode,
            recent_category_count=request.recent_category_count,
            correlation_id=request.correlation_id or f"corr_{uuid4().hex}",
            trace_id=trace_id,
        )
        delivered_commands = getattr(service.device_gateway, "delivered_commands", [])

        return build_simulation_response(
            result=result,
            session_trace_reader=session_trace_reader,
            session_id=request.session_id,
            delivered_commands=delivered_commands,
            trace_id=trace_id,
        )

    @app.post(
        "/api/simulations/documents/contract-review",
        response_model=SimulationResponse,
    )
    def simulate_contract_review(
        request: DocumentContractReviewRequest,
        service: Annotated[DocumentSessionService, Depends(get_document_session_service)],
        session_trace_reader: Annotated[GetSessionTrace, Depends(get_session_trace_reader)],
    ) -> SimulationResponse:
        if not request.document_text and not request.document_image_base64:
            raise HTTPException(
                status_code=422,
                detail="document_text_or_document_image_base64_required",
            )
        trace_id = request.trace_id or f"trace_{uuid4().hex}"
        result = service.process_contract_review(
            observation_id=request.observation_id or f"obs_{uuid4().hex}",
            user_id=request.user_id,
            session_id=request.session_id,
            document_text=request.document_text,
            document_image_base64=request.document_image_base64,
            confidence=request.confidence,
            mode=request.mode,
            recent_category_count=request.recent_category_count,
            correlation_id=request.correlation_id or f"corr_{uuid4().hex}",
            trace_id=trace_id,
        )
        delivered_commands = getattr(service.device_gateway, "delivered_commands", [])

        return build_simulation_response(
            result=result,
            session_trace_reader=session_trace_reader,
            session_id=request.session_id,
            delivered_commands=delivered_commands,
            trace_id=trace_id,
            analysis=result.analysis.to_dict(),
            analysis_id=result.analysis_record.analysis_id,
        )

    @app.get(
        "/api/sessions/{session_id}/trace",
        response_model=SessionTraceResponse,
    )
    def get_session_trace(
        session_id: str,
        trace_id: str | None = None,
        reader: Annotated[GetSessionTrace, Depends(get_session_trace_reader)] = None,
    ) -> SessionTraceResponse:
        trace = reader.execute(session_id=session_id, trace_id=trace_id)
        return SessionTraceResponse(**trace.to_dict())

    @app.get(
        "/api/sessions/{session_id}/document-analyses",
        response_model=list[DocumentAnalysisResponse],
    )
    def list_document_analyses_by_session(
        session_id: str,
        reader: Annotated[
            ListDocumentAnalysesBySession,
            Depends(get_document_analyses_by_session_reader),
        ],
    ) -> list[DocumentAnalysisResponse]:
        records = reader.execute(session_id=session_id)
        return [serialize_document_analysis(record) for record in records]

    @app.get(
        "/api/document-analyses/{analysis_id}",
        response_model=DocumentAnalysisResponse,
    )
    def get_document_analysis(
        analysis_id: str,
        reader: Annotated[GetDocumentAnalysis, Depends(get_document_analysis_reader)],
    ) -> DocumentAnalysisResponse:
        record = reader.execute(analysis_id=analysis_id)
        if record is None:
            raise HTTPException(status_code=404, detail="document_analysis_not_found")
        return serialize_document_analysis(record)

    @app.post(
        "/api/jobs/documents/contract-analysis",
        response_model=JobResponse,
    )
    def enqueue_document_analysis_job(
        request: DocumentAnalysisJobRequest,
        enqueuer=Depends(get_document_job_enqueuer),
        worker=Depends(get_document_job_worker),
    ) -> JobResponse:
        if not request.document_text and not request.document_image_base64:
            raise HTTPException(
                status_code=422,
                detail="document_text_or_document_image_base64_required",
            )
        trace_id = request.trace_id or f"trace_{uuid4().hex}"
        job = enqueuer.execute(
            user_id=request.user_id,
            session_id=request.session_id,
            idempotency_key=request.idempotency_key,
            correlation_id=request.correlation_id or f"corr_{uuid4().hex}",
            trace_id=trace_id,
            artifact_label=request.artifact_label,
            source_type=request.source_type,
            document_text=request.document_text,
            document_image_base64=request.document_image_base64,
            confidence=request.confidence,
            mode=request.mode,
            recent_category_count=request.recent_category_count,
            observation_id=request.observation_id,
        )
        if job.status == JobStatus.QUEUED:
            worker.enqueue(job.job_id)
        return serialize_job(job)

    @app.get("/api/jobs/{job_id}", response_model=JobResponse)
    def get_job_status(
        job_id: str,
        reader: Annotated[GetJobStatus, Depends(get_job_status_reader)],
    ) -> JobResponse:
        job = reader.execute(job_id=job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job_not_found")
        return serialize_job(job)

    @app.post("/api/jobs/{job_id}/status", response_model=JobResponse)
    def advance_job_status(
        job_id: str,
        request: JobTransitionRequest,
        advancer: Annotated[AdvanceDocumentAnalysisJob, Depends(get_document_job_advancer)],
    ) -> JobResponse:
        trace_id = request.trace_id or f"trace_{uuid4().hex}"
        try:
            job = advancer.execute(
                job_id=job_id,
                target_status=request.target_status,
                analysis_id=request.analysis_id,
                error_code=request.error_code,
                error_message=request.error_message,
                correlation_id=request.correlation_id or f"corr_{uuid4().hex}",
                trace_id=trace_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if job is None:
            raise HTTPException(status_code=404, detail="job_not_found")
        return serialize_job(job)

    @app.get(
        "/api/jobs/{job_id}/result",
        response_model=DocumentAnalysisResponse,
    )
    def get_document_job_result(
        job_id: str,
        job_reader: Annotated[GetJobStatus, Depends(get_job_status_reader)],
        analysis_reader: Annotated[GetDocumentAnalysis, Depends(get_document_analysis_reader)],
    ) -> DocumentAnalysisResponse:
        job = job_reader.execute(job_id=job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job_not_found")
        if job.status != JobStatus.SUCCEEDED or not job.result_id:
            raise HTTPException(status_code=409, detail="job_result_not_ready")
        record = analysis_reader.execute(analysis_id=job.result_id)
        if record is None:
            raise HTTPException(status_code=404, detail="job_result_not_found")
        return serialize_document_analysis(record)

    @app.post(
        "/api/lens-commands/{command_id}/feedback",
        response_model=LensFeedbackResponse,
    )
    def record_lens_feedback(
        command_id: str,
        request: LensFeedbackRequest,
        recorder: Annotated[RecordLensFeedback, Depends(get_lens_feedback_recorder)],
    ) -> LensFeedbackResponse:
        result = recorder.execute(
            command_id=command_id,
            user_id=request.user_id,
            session_id=request.session_id,
            feedback=request.feedback,
            correlation_id=request.correlation_id or f"corr_{uuid4().hex}",
            trace_id=request.trace_id,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="lens_command_not_found")
        return LensFeedbackResponse(
            event_id=result.event_id,
            command_id=result.command_id,
            feedback=result.feedback.value,
        )

    return app
