from __future__ import annotations

from contextlib import asynccontextmanager
from os import environ
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from new_era.application.services import GrocerySessionService, SimulationRuntime
from new_era.application.use_cases import (
    GetSessionTrace,
)
from new_era.application.use_cases import (
    GetUserSession,
    ListUserSessions,
    RecordLensFeedback,
    SessionOwnershipError,
    StartUserSession,
)
from new_era.application.ports import DeviceGateway
from new_era.domain.events import EventType
from new_era.infrastructure.http.auth import (
    AUTH_SESSION_COOKIE,
    InMemoryAuthSessionStore,
    LocalPasswordAuthConfig,
    SQLiteAuthSessionStore,
)
from new_era.infrastructure.http.dependencies import (
    enforce_same_origin_browser_write,
    get_authenticated_identity,
    get_current_user_id,
    get_device_gateway,
    get_grocery_session_service,
    get_lens_feedback_recorder,
    get_optional_authenticated_identity,
    get_session_trace_reader,
    get_user_session_reader,
    get_user_session_starter,
    get_user_sessions_lister,
)
from new_era.infrastructure.http.document_routes import create_document_router
from new_era.infrastructure.http.schemas import (
    AuthLoginRequest,
    AuthSessionStateResponse,
    CurrentUserResponse,
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
    enable_dev_auth: bool | None = None,
    local_user_id: str | None = None,
    local_auth_user_id: str | None = None,
    local_auth_password: str | None = None,
) -> FastAPI:
    configured_storage_path = storage_path or environ.get("NEW_ERA_SQLITE_PATH")
    runtime = SimulationRuntime.build_default(
        storage_path=configured_storage_path,
        device_gateway=device_gateway,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.runtime.document_job_worker.stop()

    app = FastAPI(title="New Era Glasses API", version="0.1.0", lifespan=lifespan)
    static_dir = Path(__file__).with_name("static")
    runtime_root = (
        Path(configured_storage_path).parent
        if configured_storage_path is not None
        else Path(environ.get("NEW_ERA_RUNTIME_DIR", ".new_era"))
    )
    upload_dir = runtime_root / "uploads" / "documents"
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.state.runtime = runtime
    app.state.enable_dev_auth = (
        enable_dev_auth
        if enable_dev_auth is not None
        else environ.get("NEW_ERA_ENABLE_DEV_AUTH") == "1"
    )
    app.state.local_user_id = local_user_id or environ.get("NEW_ERA_LOCAL_USER_ID")
    app.state.local_password_auth = LocalPasswordAuthConfig(
        user_id=local_auth_user_id or environ.get("NEW_ERA_LOCAL_AUTH_USER_ID"),
        password=local_auth_password or environ.get("NEW_ERA_LOCAL_AUTH_PASSWORD"),
    )
    app.state.auth_session_store = (
        SQLiteAuthSessionStore(configured_storage_path)
        if configured_storage_path is not None
        else InMemoryAuthSessionStore()
    )
    app.state.upload_dir = upload_dir

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.include_router(create_document_router(static_dir=static_dir))

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/api/auth/session", response_model=AuthSessionStateResponse)
    def get_auth_session(
        identity=Depends(get_authenticated_identity),
    ) -> AuthSessionStateResponse:
        return AuthSessionStateResponse(
            authenticated=True,
            current_user=CurrentUserResponse(user_id=identity.user_id),
            auth_session={
                "auth_session_id": identity.auth_session_id,
                "auth_method": identity.auth_method,
                "expires_at": identity.expires_at.isoformat(),
            },
        )

    @app.post("/api/auth/login", response_model=AuthSessionStateResponse)
    def login(
        request: AuthLoginRequest,
        response: Response,
        http_request: Request,
        _: Annotated[None, Depends(enforce_same_origin_browser_write)],
    ) -> AuthSessionStateResponse:
        local_password_auth = app.state.local_password_auth
        if not local_password_auth.is_configured:
            raise HTTPException(status_code=503, detail="local_auth_not_configured")
        if not local_password_auth.authenticate(
            user_id=request.user_id,
            password=request.password,
        ):
            raise HTTPException(status_code=401, detail="invalid_credentials")
        record = app.state.auth_session_store.create(
            user_id=request.user_id,
            auth_method="local_password",
        )
        secure_cookie = http_request.url.hostname not in {"127.0.0.1", "localhost", "testserver"}
        response.set_cookie(
            key=AUTH_SESSION_COOKIE,
            value=record.auth_session_id,
            httponly=True,
            samesite="lax",
            secure=secure_cookie,
            max_age=int(app.state.auth_session_store.ttl.total_seconds()),
            path="/",
        )
        return AuthSessionStateResponse(
            authenticated=True,
            current_user=CurrentUserResponse(user_id=record.user_id),
            auth_session={
                "auth_session_id": record.auth_session_id,
                "auth_method": record.auth_method,
                "expires_at": record.expires_at.isoformat(),
            },
        )

    @app.post("/api/auth/logout", status_code=204)
    def logout(
        response: Response,
        identity=Depends(get_optional_authenticated_identity),
        _: Annotated[None, Depends(enforce_same_origin_browser_write)] = None,
    ) -> Response:
        if identity is not None and identity.auth_session_id.startswith("authsess_"):
            app.state.auth_session_store.invalidate(identity.auth_session_id)
        response = Response(status_code=204)
        response.delete_cookie(key=AUTH_SESSION_COOKIE, path="/")
        return response

    def _read_session_trace_for(
        *,
        user_id: str,
        session_id: str,
        trace_id: str | None,
        module: str | None,
        event_type: list[EventType] | None,
        step: list[str] | None,
        created_after: str | None,
        created_before: str | None,
        limit: int | None,
        cursor: str | None,
        reader: GetSessionTrace,
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

    def _read_owned_session_trace_for(
        *,
        user_id: str,
        session_id: str,
        trace_id: str | None,
        module: str | None,
        event_type: list[EventType] | None,
        step: list[str] | None,
        created_after: str | None,
        created_before: str | None,
        limit: int | None,
        cursor: str | None,
        session_reader: GetUserSession,
        trace_reader: GetSessionTrace,
    ) -> SessionTraceResponse:
        session = session_reader.execute(user_id=user_id, session_id=session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session_not_found")
        ensure_session_owned_by_current_user(session, user_id)
        return _read_session_trace_for(
            user_id=user_id,
            session_id=session_id,
            trace_id=trace_id,
            module=module,
            event_type=event_type,
            step=step,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
            cursor=cursor,
            reader=trace_reader,
        )

    def _create_user_session_for(
        *,
        user_id: str,
        request: CreateUserSessionRequest,
        starter: StartUserSession,
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

    def _list_user_sessions_for(
        *,
        user_id: str,
        module: str | None,
        limit: int | None,
        cursor: str | None,
        lister: ListUserSessions,
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
        _: Annotated[None, Depends(enforce_same_origin_browser_write)],
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
        return _read_session_trace_for(
            user_id=scoped_user_id,
            session_id=session_id,
            trace_id=trace_id,
            module=module,
            event_type=event_type,
            step=step,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
            cursor=cursor,
            reader=reader,
        )

    @app.get(
        "/api/current-user/sessions/{session_id}/trace",
        response_model=SessionTraceResponse,
    )
    def get_current_user_session_trace(
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
        return _read_owned_session_trace_for(
            user_id=current_user_id,
            session_id=session_id,
            trace_id=trace_id,
            module=module,
            event_type=event_type,
            step=step,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
            cursor=cursor,
            session_reader=session_reader,
            trace_reader=trace_reader,
        )

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
        authenticated_user_id = enforce_path_user(user_id, current_user_id)
        return _read_owned_session_trace_for(
            user_id=authenticated_user_id,
            session_id=session_id,
            trace_id=trace_id,
            module=module,
            event_type=event_type,
            step=step,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
            cursor=cursor,
            session_reader=session_reader,
            trace_reader=trace_reader,
        )

    @app.post(
        "/api/current-user/sessions",
        response_model=UserSessionResponse,
    )
    def create_current_user_session(
        request: CreateUserSessionRequest,
        starter: Annotated[StartUserSession, Depends(get_user_session_starter)],
        current_user_id: Annotated[str, Depends(get_current_user_id)],
        _: Annotated[None, Depends(enforce_same_origin_browser_write)],
    ) -> UserSessionResponse:
        return _create_user_session_for(
            user_id=current_user_id,
            request=request,
            starter=starter,
        )

    @app.post(
        "/api/users/{user_id}/sessions",
        response_model=UserSessionResponse,
    )
    def create_user_session(
        user_id: str,
        request: CreateUserSessionRequest,
        starter: Annotated[StartUserSession, Depends(get_user_session_starter)],
        current_user_id: Annotated[str, Depends(get_current_user_id)],
        _: Annotated[None, Depends(enforce_same_origin_browser_write)],
    ) -> UserSessionResponse:
        authenticated_user_id = enforce_path_user(user_id, current_user_id)
        return _create_user_session_for(
            user_id=authenticated_user_id,
            request=request,
            starter=starter,
        )

    @app.get(
        "/api/current-user/sessions",
        response_model=UserSessionPageResponse,
    )
    def list_current_user_sessions(
        module: str | None = None,
        limit: int | None = Query(default=None, ge=1, le=100),
        cursor: str | None = None,
        lister: Annotated[ListUserSessions, Depends(get_user_sessions_lister)] = None,
        current_user_id: Annotated[str, Depends(get_current_user_id)] = "",
    ) -> UserSessionPageResponse:
        return _list_user_sessions_for(
            user_id=current_user_id,
            module=module,
            limit=limit,
            cursor=cursor,
            lister=lister,
        )

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
        authenticated_user_id = enforce_path_user(user_id, current_user_id)
        return _list_user_sessions_for(
            user_id=authenticated_user_id,
            module=module,
            limit=limit,
            cursor=cursor,
            lister=lister,
        )

    @app.post(
        "/api/lens-commands/{command_id}/feedback",
        response_model=LensFeedbackResponse,
    )
    def record_lens_feedback(
        command_id: str,
        request: LensFeedbackRequest,
        recorder: Annotated[RecordLensFeedback, Depends(get_lens_feedback_recorder)],
        current_user_id: Annotated[str, Depends(get_current_user_id)],
        _: Annotated[None, Depends(enforce_same_origin_browser_write)],
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
