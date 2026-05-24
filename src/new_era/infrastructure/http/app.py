from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
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
from new_era.application.use_cases import (
    GetUserSession,
    ListUserSessions,
    SessionOwnershipError,
    StartUserSession,
)
from new_era.application.ports import DeviceGateway
from new_era.domain.documents import DocumentAnalysisRecord
from new_era.domain.attention import AttentionMode
from new_era.domain.events import EventType
from new_era.domain.jobs import JobRecord, JobStatus
from new_era.domain.sessions import UserSession


class HealthResponse(BaseModel):
    status: str


class GroceryMissingItemRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_id: str
    session_id: str | None = None
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
    session_id: str | None = None
    document_text: str | None = Field(default=None, min_length=20)
    document_image_base64: str | None = None
    confidence: float | None = Field(default=0.92, ge=0, le=1)
    mode: AttentionMode = AttentionMode.BALANCED
    recent_category_count: int = Field(ge=0, default=0)
    observation_id: str | None = None
    correlation_id: str | None = None
    trace_id: str | None = None


class SimulationResponse(BaseModel):
    session_id: str
    outcome: str
    candidate_created: bool
    command: dict[str, object] | None
    event_count: int
    delivered_commands_count: int
    session_trace: list[dict[str, object]]
    analysis: dict[str, object] | None = None
    analysis_id: str | None = None


class DeviceCapabilitiesResponse(BaseModel):
    adapter_name: str
    supports_camera: bool
    supports_display: bool
    supports_voice: bool
    supports_gesture: bool
    unsupported_features: list[str]
    metadata: dict[str, object]


class CameraDocumentContractReviewRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_id: str
    session_id: str | None = None
    image_base64: str = Field(min_length=1)
    content_type: str = Field(default="image/jpeg", min_length=1)
    source_adapter: str = Field(
        default="phone_camera",
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9_:-]+$",
    )
    mode: AttentionMode = AttentionMode.BALANCED
    recent_category_count: int = Field(ge=0, default=0)
    observation_id: str | None = None
    correlation_id: str | None = None
    trace_id: str | None = None


class SessionTraceResponse(BaseModel):
    session_id: str
    trace_id: str | None
    event_count: int
    next_cursor: str | None = None
    session_trace: list[dict[str, object]]


class CreateUserSessionRequest(BaseModel):
    module: str = Field(min_length=1)
    title: str | None = Field(default=None, min_length=1)
    session_id: str | None = Field(default=None, min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)


class UserSessionResponse(BaseModel):
    session_id: str
    user_id: str
    module: str
    title: str
    created_at: str
    updated_at: str
    metadata: dict[str, object]


class UserSessionPageResponse(BaseModel):
    user_id: str
    session_count: int
    next_cursor: str | None
    sessions: list[UserSessionResponse]


class DocumentAnalysisJobRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_id: str
    session_id: str | None = None
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


def serialize_device_capabilities(capabilities) -> DeviceCapabilitiesResponse:
    return DeviceCapabilitiesResponse(
        adapter_name=capabilities.adapter_name,
        supports_camera=capabilities.supports_camera,
        supports_display=capabilities.supports_display,
        supports_voice=capabilities.supports_voice,
        supports_gesture=capabilities.supports_gesture,
        unsupported_features=list(capabilities.unsupported_features),
        metadata=dict(capabilities.metadata),
    )


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


def get_user_session_starter(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> StartUserSession:
    return runtime.user_session_starter


def get_user_session_reader(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> GetUserSession:
    return runtime.user_session_reader


def get_user_sessions_lister(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> ListUserSessions:
    return runtime.user_sessions_lister


def get_device_gateway(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> DeviceGateway:
    return runtime.device_gateway


def serialize_user_session(session: UserSession) -> UserSessionResponse:
    return UserSessionResponse(**session.to_dict())


def resolve_user_session(
    *,
    starter: StartUserSession,
    user_id: str,
    module: str,
    session_id: str | None,
) -> UserSession:
    try:
        return starter.execute(
            user_id=user_id,
            module=module,
            session_id=session_id,
        )
    except SessionOwnershipError as exc:
        raise HTTPException(status_code=403, detail="session_does_not_belong_to_user") from exc


def parse_datetime_query(value: str | None, *, field_name: str) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid_{field_name}") from exc


def validate_camera_content_type(content_type: str) -> None:
    normalized = content_type.lower().split(";", 1)[0].strip()
    supported_types = {"image/jpeg", "image/png", "image/webp"}
    if normalized not in supported_types:
        raise HTTPException(status_code=415, detail="unsupported_camera_content_type")


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
    delivered_commands_count = sum(
        1
        for entry in session_trace.session_trace
        if entry.event_type == EventType.LENS_COMMAND_DELIVERED.value
    )
    return SimulationResponse(
        session_id=session_id,
        outcome=result.outcome.value,
        candidate_created=result.candidate_created,
        command=result.alert_result.command.to_dict()
        if result.alert_result and result.alert_result.command
            else None,
        event_count=session_trace.event_count,
        delivered_commands_count=delivered_commands_count,
        session_trace=[entry.to_dict() for entry in session_trace.session_trace],
        analysis=analysis,
        analysis_id=analysis_id,
    )


def create_app(
    *,
    storage_path: str | Path | None = None,
    device_gateway: DeviceGateway | None = None,
) -> FastAPI:
    runtime = SimulationRuntime.build_default(
        storage_path=storage_path,
        device_gateway=device_gateway,
    )

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

    @app.get("/api/device/capabilities", response_model=DeviceCapabilitiesResponse)
    def get_device_capabilities(
        gateway: Annotated[DeviceGateway, Depends(get_device_gateway)],
    ) -> DeviceCapabilitiesResponse:
        return serialize_device_capabilities(gateway.capabilities())

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
        session_starter: Annotated[StartUserSession, Depends(get_user_session_starter)],
    ) -> SimulationResponse:
        session = resolve_user_session(
            starter=session_starter,
            user_id=request.user_id,
            module="grocery",
            session_id=request.session_id,
        )
        trace_id = request.trace_id or f"trace_{uuid4().hex}"
        result = service.process_missing_item(
            observation_id=request.observation_id or f"obs_{uuid4().hex}",
            user_id=request.user_id,
            session_id=session.session_id,
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
            session_id=session.session_id,
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
        session_starter: Annotated[StartUserSession, Depends(get_user_session_starter)],
    ) -> SimulationResponse:
        if not request.document_text and not request.document_image_base64:
            raise HTTPException(
                status_code=422,
                detail="document_text_or_document_image_base64_required",
            )
        session = resolve_user_session(
            starter=session_starter,
            user_id=request.user_id,
            module="documents",
            session_id=request.session_id,
        )
        trace_id = request.trace_id or f"trace_{uuid4().hex}"
        result = service.process_contract_review(
            observation_id=request.observation_id or f"obs_{uuid4().hex}",
            user_id=request.user_id,
            session_id=session.session_id,
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
            session_id=session.session_id,
            delivered_commands=delivered_commands,
            trace_id=trace_id,
            analysis=result.analysis.to_dict(),
            analysis_id=result.analysis_record.analysis_id,
        )

    @app.post(
        "/api/device-bridge/camera/document-contract-review",
        response_model=SimulationResponse,
    )
    def process_camera_contract_review(
        request: CameraDocumentContractReviewRequest,
        service: Annotated[DocumentSessionService, Depends(get_document_session_service)],
        session_trace_reader: Annotated[GetSessionTrace, Depends(get_session_trace_reader)],
        session_starter: Annotated[StartUserSession, Depends(get_user_session_starter)],
    ) -> SimulationResponse:
        validate_camera_content_type(request.content_type)
        session = resolve_user_session(
            starter=session_starter,
            user_id=request.user_id,
            module="documents",
            session_id=request.session_id,
        )
        trace_id = request.trace_id or f"trace_{uuid4().hex}"
        result = service.process_contract_review(
            observation_id=request.observation_id or f"obs_{uuid4().hex}",
            user_id=request.user_id,
            session_id=session.session_id,
            document_text=None,
            document_image_base64=request.image_base64,
            confidence=None,
            mode=request.mode,
            recent_category_count=request.recent_category_count,
            correlation_id=request.correlation_id or f"corr_{uuid4().hex}",
            trace_id=trace_id,
            source_type=f"camera:{request.source_adapter}",
            observation_summary=(
                "Contract review requested from camera bridge "
                f"via {request.source_adapter}"
            ),
        )

        return build_simulation_response(
            result=result,
            session_trace_reader=session_trace_reader,
            session_id=session.session_id,
            delivered_commands=[],
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
        user_id: str | None = None,
        trace_id: str | None = None,
        module: str | None = None,
        event_type: Annotated[list[EventType] | None, Query()] = None,
        step: Annotated[list[str] | None, Query()] = None,
        created_after: str | None = None,
        created_before: str | None = None,
        limit: int | None = Query(default=None, ge=1, le=100),
        cursor: str | None = None,
        reader: Annotated[GetSessionTrace, Depends(get_session_trace_reader)] = None,
    ) -> SessionTraceResponse:
        try:
            trace = reader.execute(
                session_id=session_id,
                user_id=user_id,
                trace_id=trace_id,
                module=module,
                event_types=set(event_type) if event_type else None,
                steps=set(step) if step else None,
                created_after=parse_datetime_query(
                    created_after,
                    field_name="created_after",
                ),
                created_before=parse_datetime_query(
                    created_before,
                    field_name="created_before",
                ),
                limit=limit,
                cursor=cursor,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return SessionTraceResponse(**trace.to_dict())

    @app.get(
        "/api/users/{user_id}/sessions/{session_id}/trace",
        response_model=SessionTraceResponse,
    )
    def get_user_session_trace(
        user_id: str,
        session_id: str,
        trace_id: str | None = None,
        module: str | None = None,
        event_type: Annotated[list[EventType] | None, Query()] = None,
        step: Annotated[list[str] | None, Query()] = None,
        created_after: str | None = None,
        created_before: str | None = None,
        limit: int | None = Query(default=None, ge=1, le=100),
        cursor: str | None = None,
        session_reader: Annotated[GetUserSession, Depends(get_user_session_reader)] = None,
        trace_reader: Annotated[GetSessionTrace, Depends(get_session_trace_reader)] = None,
    ) -> SessionTraceResponse:
        if session_reader.execute(user_id=user_id, session_id=session_id) is None:
            raise HTTPException(status_code=404, detail="session_not_found")
        try:
            trace = trace_reader.execute(
                session_id=session_id,
                user_id=user_id,
                trace_id=trace_id,
                module=module,
                event_types=set(event_type) if event_type else None,
                steps=set(step) if step else None,
                created_after=parse_datetime_query(
                    created_after,
                    field_name="created_after",
                ),
                created_before=parse_datetime_query(
                    created_before,
                    field_name="created_before",
                ),
                limit=limit,
                cursor=cursor,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return SessionTraceResponse(**trace.to_dict())

    @app.post(
        "/api/users/{user_id}/sessions",
        response_model=UserSessionResponse,
    )
    def create_user_session(
        user_id: str,
        request: CreateUserSessionRequest,
        starter: Annotated[StartUserSession, Depends(get_user_session_starter)],
    ) -> UserSessionResponse:
        try:
            session = starter.execute(
                user_id=user_id,
                module=request.module,
                title=request.title,
                session_id=request.session_id,
                metadata=request.metadata,
            )
        except SessionOwnershipError as exc:
            raise HTTPException(status_code=403, detail="session_does_not_belong_to_user") from exc
        return serialize_user_session(session)

    @app.get(
        "/api/users/{user_id}/sessions",
        response_model=UserSessionPageResponse,
    )
    def list_user_sessions(
        user_id: str,
        module: str | None = None,
        limit: int | None = Query(default=None, ge=1, le=100),
        cursor: str | None = None,
        lister: Annotated[ListUserSessions, Depends(get_user_sessions_lister)] = None,
    ) -> UserSessionPageResponse:
        try:
            page = lister.execute(
                user_id=user_id,
                module=module,
                limit=limit,
                cursor=cursor,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return UserSessionPageResponse(**page.to_dict())

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
        session_starter: Annotated[StartUserSession, Depends(get_user_session_starter)],
        enqueuer=Depends(get_document_job_enqueuer),
        worker=Depends(get_document_job_worker),
    ) -> JobResponse:
        if not request.document_text and not request.document_image_base64:
            raise HTTPException(
                status_code=422,
                detail="document_text_or_document_image_base64_required",
            )
        session = resolve_user_session(
            starter=session_starter,
            user_id=request.user_id,
            module="documents",
            session_id=request.session_id,
        )
        trace_id = request.trace_id or f"trace_{uuid4().hex}"
        job = enqueuer.execute(
            user_id=request.user_id,
            session_id=session.session_id,
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
