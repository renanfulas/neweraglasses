from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

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

LOCAL_AUTH_HEADER = "X-New-Era-User-Id"


def get_runtime(request: Request) -> SimulationRuntime:
    return request.app.state.runtime


def get_current_user_id(
    request: Request,
    x_new_era_user_id: Annotated[str | None, Header(alias=LOCAL_AUTH_HEADER)] = None,
) -> str:
    authenticated_user_id = x_new_era_user_id or getattr(request.app.state, "local_user_id", None)
    if not authenticated_user_id:
        raise HTTPException(status_code=401, detail="local_auth_user_required")
    return authenticated_user_id


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
