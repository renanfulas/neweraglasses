from __future__ import annotations

from base64 import b64encode
from contextlib import asynccontextmanager
from os import environ
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from new_era.application.services import GrocerySessionService, SimulationRuntime
from new_era.application.use_cases import (
    GetSessionTrace,
)
from new_era.application.use_cases import LensFeedbackValue, RecordLensFeedback
from new_era.application.use_cases import (
    GetUserSession,
    ListUserSessions,
    StartUserSession,
)
from new_era.application.ports import DeviceGateway
from new_era.domain.events import EventType
from new_era.domain.jobs import JobStatus
from new_era.domain.sessions import UserSession
from new_era.infrastructure.http.dependencies import (
    get_current_user_id,
    get_device_gateway,
    get_grocery_session_service,
    get_job_session_lister,
    get_lens_feedback_recorder,
    get_session_trace_reader,
    get_user_session_reader,
    get_user_session_starter,
    get_user_sessions_lister,
)
from new_era.infrastructure.http.document_routes import create_document_router
from new_era.infrastructure.http.schemas import (
    CreateUserSessionRequest,
    DeviceCapabilitiesResponse,
    GroceryMissingItemRequest,
    HealthResponse,
    JobPageResponse,
    LensFeedbackRequest,
    LensFeedbackResponse,
    SessionTraceResponse,
    SimulationResponse,
    UserSessionPageResponse,
    UserSessionResponse,
    serialize_device_capabilities,
    serialize_user_session,
)
from new_era.infrastructure.http.support import (
    build_simulation_response,
    enforce_authenticated_user,
    enforce_path_user,
    ensure_session_owned_by_current_user,
    parse_datetime_query,
    resolve_user_session,
)


def create_app(
    *,
    storage_path: str | Path | None = None,
    device_gateway: DeviceGateway | None = None,
    local_user_id: str | None = None,
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
    runtime_root = (
        Path(storage_path).parent
        if storage_path is not None
        else Path(environ.get("NEW_ERA_RUNTIME_DIR", ".new_era"))
    )
    upload_dir = runtime_root / "uploads" / "documents"
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.state.runtime = runtime
    app.state.local_user_id = local_user_id or environ.get("NEW_ERA_LOCAL_USER_ID")
    app.state.upload_dir = upload_dir

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.include_router(create_document_router(static_dir=static_dir))

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
        current_user_id: Annotated[str, Depends(get_current_user_id)],
    ) -> SimulationResponse:
        user_id = enforce_authenticated_user(request.user_id, current_user_id)
        session = resolve_user_session(
            starter=session_starter,
            user_id=user_id,
            module="grocery",
            session_id=request.session_id,
        )
        trace_id = request.trace_id or f"trace_{uuid4().hex}"
        result = service.process_missing_item(
            observation_id=request.observation_id or f"obs_{uuid4().hex}",
            user_id=user_id,
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
        current_user_id: Annotated[str, Depends(get_current_user_id)] = "",
    ) -> SessionTraceResponse:
        scoped_user_id = current_user_id if user_id is None else enforce_authenticated_user(user_id, current_user_id)
        try:
            trace = reader.execute(
                session_id=session_id,
                user_id=scoped_user_id,
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
        current_user_id: Annotated[str, Depends(get_current_user_id)] = "",
    ) -> SessionTraceResponse:
        enforce_path_user(user_id, current_user_id)
        session = session_reader.execute(user_id=user_id, session_id=session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session_not_found")
        ensure_session_owned_by_current_user(session, current_user_id)
        try:
            trace = trace_reader.execute(
                session_id=session_id,
                user_id=current_user_id,
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
        current_user_id: Annotated[str, Depends(get_current_user_id)],
    ) -> UserSessionResponse:
        enforce_path_user(user_id, current_user_id)
        try:
            session = starter.execute(
                user_id=current_user_id,
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
        current_user_id: Annotated[str, Depends(get_current_user_id)] = "",
    ) -> UserSessionPageResponse:
        enforce_path_user(user_id, current_user_id)
        try:
            page = lister.execute(
                user_id=current_user_id,
                module=module,
                limit=limit,
                cursor=cursor,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return UserSessionPageResponse(**page.to_dict())

    @app.post(
        "/api/lens-commands/{command_id}/feedback",
        response_model=LensFeedbackResponse,
    )
    def record_lens_feedback(
        command_id: str,
        request: LensFeedbackRequest,
        recorder: Annotated[RecordLensFeedback, Depends(get_lens_feedback_recorder)],
        current_user_id: Annotated[str, Depends(get_current_user_id)],
    ) -> LensFeedbackResponse:
        user_id = enforce_authenticated_user(request.user_id, current_user_id)
        result = recorder.execute(
            command_id=command_id,
            user_id=user_id,
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
