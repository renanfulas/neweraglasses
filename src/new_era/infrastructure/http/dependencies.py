from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Cookie, Depends, Header, HTTPException, Request

from new_era.application.ports import DeviceGateway
from new_era.application.services import DocumentSessionService, GrocerySessionService, SimulationRuntime
from new_era.application.use_cases import (
    AdvanceDocumentAnalysisJob,
    DeleteLocalDocumentArtifact,
    GetDocumentAnalysis,
    GetDocumentAnalysisFeedback,
    GetDocumentFeedbackMetrics,
    GetJobStatus,
    GetRecentPolicyRejectionForSession,
    GetSessionTrace,
    GetUserSession,
    ListDocumentAnalysesBySession,
    ListJobsBySession,
    ListUserSessions,
    RecordDocumentAnalysisFeedback,
    RecordLensFeedback,
    RegisterLocalDocumentArtifact,
    StartUserSession,
)
from new_era.infrastructure.http.auth import AUTH_SESSION_COOKIE, AuthenticatedIdentity

LOCAL_AUTH_HEADER = "X-New-Era-User-Id"
SAFE_HTTP_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_runtime(request: Request) -> SimulationRuntime:
    return request.app.state.runtime


def enforce_same_origin_browser_write(
    request: Request,
    auth_session_cookie: Annotated[str | None, Cookie(alias=AUTH_SESSION_COOKIE)] = None,
    origin: Annotated[str | None, Header(alias="Origin")] = None,
) -> None:
    if request.method.upper() in SAFE_HTTP_METHODS:
        return

    is_auth_route = request.url.path.startswith("/api/auth/")
    if not auth_session_cookie and not is_auth_route:
        return

    if origin is None:
        raise HTTPException(status_code=403, detail="origin_required")

    request_origin = _normalize_origin(origin)
    expected_origin = f"{request.url.scheme}://{request.url.netloc}".lower()
    if request_origin != expected_origin:
        raise HTTPException(status_code=403, detail="cross_origin_write_forbidden")


def get_optional_authenticated_identity(
    request: Request,
    auth_session_cookie: Annotated[str | None, Cookie(alias=AUTH_SESSION_COOKIE)] = None,
    x_new_era_user_id: Annotated[str | None, Header(alias=LOCAL_AUTH_HEADER)] = None,
) -> AuthenticatedIdentity | None:
    auth_session_store = getattr(request.app.state, "auth_session_store", None)
    if auth_session_cookie and auth_session_store is not None:
        record = auth_session_store.get(auth_session_cookie)
        if record is not None:
            return record.to_identity()

    enable_dev_auth = bool(getattr(request.app.state, "enable_dev_auth", False))
    if x_new_era_user_id and not enable_dev_auth:
        raise HTTPException(status_code=401, detail="dev_header_auth_disabled")
    if enable_dev_auth and x_new_era_user_id:
        current_time = datetime.now(UTC)
        return AuthenticatedIdentity(
            subject_id=x_new_era_user_id,
            user_id=x_new_era_user_id,
            auth_session_id="dev_header_auth",
            auth_method="dev_header",
            issued_at=current_time,
            expires_at=current_time,
        )

    local_user_id = getattr(request.app.state, "local_user_id", None)
    if enable_dev_auth and local_user_id:
        current_time = datetime.now(UTC)
        return AuthenticatedIdentity(
            subject_id=local_user_id,
            user_id=local_user_id,
            auth_session_id="dev_local_auth",
            auth_method="dev_local_fallback",
            issued_at=current_time,
            expires_at=current_time,
        )
    return None


def get_authenticated_identity(
    identity: Annotated[
        AuthenticatedIdentity | None,
        Depends(get_optional_authenticated_identity),
    ],
) -> AuthenticatedIdentity:
    if identity is None:
        raise HTTPException(status_code=401, detail="auth_session_required")
    return identity


def get_current_user_id(
    identity: Annotated[AuthenticatedIdentity, Depends(get_authenticated_identity)],
) -> str:
    return identity.user_id


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


def get_job_session_lister(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> ListJobsBySession:
    return runtime.job_session_lister


def get_recent_policy_rejection_reader(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> GetRecentPolicyRejectionForSession:
    return GetRecentPolicyRejectionForSession(
        event_store=runtime.event_store,
        job_store=runtime.job_store,
        artifact_store=runtime.document_artifact_store,
    )


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


def get_document_analysis_feedback_reader(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> GetDocumentAnalysisFeedback:
    return runtime.document_analysis_feedback_reader


def get_document_analysis_feedback_recorder(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> RecordDocumentAnalysisFeedback:
    return runtime.document_analysis_feedback_recorder


def get_document_artifact_registrar(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> RegisterLocalDocumentArtifact:
    return runtime.document_artifact_registrar


def get_document_artifact_deleter(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> DeleteLocalDocumentArtifact:
    return runtime.document_artifact_deleter


def get_document_feedback_metrics_reader(
    runtime: Annotated[SimulationRuntime, Depends(get_runtime)],
) -> GetDocumentFeedbackMetrics:
    return runtime.document_feedback_metrics_reader


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


def _normalize_origin(origin: str) -> str:
    parsed = urlsplit(origin)
    if not parsed.scheme or not parsed.netloc:
        raise HTTPException(status_code=403, detail="invalid_origin")
    return f"{parsed.scheme}://{parsed.netloc}".lower()
