from __future__ import annotations

from base64 import b64encode
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from new_era.application.services import DocumentSessionService
from new_era.application.use_cases import (
    AdvanceDocumentAnalysisJob,
    DeleteLocalDocumentArtifact,
    DocumentArtifactNotFoundError,
    DocumentArtifactOwnershipError,
    DocumentArtifactQuotaExceededError,
    GetDocumentAnalysis,
    GetDocumentAnalysisFeedback,
    GetDocumentFeedbackMetrics,
    GetJobStatus,
    GetRecentPolicyRejectionForSession,
    PolicyRejectedError,
    PolicyRejection,
    GetSessionTrace,
    GetUserSession,
    ListDocumentAnalysesBySession,
    ListJobsBySession,
    RecordDocumentAnalysisFeedback,
    StartUserSession,
)
from new_era.domain.attention import AttentionMode
from new_era.domain.jobs import JobStatus
from new_era.infrastructure.http.dependencies import (
    get_current_user_id,
    get_document_analysis_feedback_reader,
    get_document_analysis_feedback_recorder,
    get_document_analysis_reader,
    get_document_artifact_deleter,
    get_document_artifact_registrar,
    get_document_feedback_metrics_reader,
    get_document_job_advancer,
    get_document_job_enqueuer,
    get_document_job_worker,
    get_document_session_service,
    get_document_analyses_by_session_reader,
    get_job_session_lister,
    get_job_status_reader,
    get_recent_policy_rejection_reader,
    get_session_trace_reader,
    get_user_session_reader,
    get_user_session_starter,
)
from new_era.infrastructure.http.schemas import (
    CameraDocumentContractReviewRequest,
    DocumentAnalysisFeedbackRequest,
    DocumentAnalysisFeedbackResponse,
    DocumentAnalysisJobRequest,
    DocumentAnalysisResponse,
    DocumentArtifactDeleteResponse,
    DocumentContractReviewRequest,
    DocumentFeedbackMetricsResponse,
    JobPageResponse,
    JobResponse,
    JobTransitionRequest,
    SimulationResponse,
    serialize_document_analysis,
    serialize_document_feedback_metrics,
    serialize_job,
    serialize_policy_rejection,
)
from new_era.infrastructure.http.support import (
    build_simulation_response,
    ensure_document_analysis_owned_by_current_user,
    ensure_job_owned_by_current_user,
    ensure_session_owned_by_current_user,
    enforce_authenticated_user,
    enforce_path_user,
    policy_status_code_for,
    read_upload_bytes,
    raise_rejected_http_error,
    raise_policy_http_error,
    resolve_document_analysis_feedback,
    resolve_user_session,
    safe_upload_filename,
    upload_extension_for,
    validate_camera_content_type,
    validate_upload_content_type,
)


def create_document_router(*, static_dir: Path) -> APIRouter:
    router = APIRouter()

    @router.get("/document-analyses/{analysis_id}/view")
    def analysis_detail_page(analysis_id: str) -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @router.post(
        "/api/simulations/documents/contract-review",
        response_model=SimulationResponse,
    )
    def simulate_contract_review(
        request: DocumentContractReviewRequest,
        service: Annotated[DocumentSessionService, Depends(get_document_session_service)],
        session_trace_reader: Annotated[GetSessionTrace, Depends(get_session_trace_reader)],
        session_starter: Annotated[StartUserSession, Depends(get_user_session_starter)],
        current_user_id: Annotated[str, Depends(get_current_user_id)],
    ) -> SimulationResponse:
        if not request.document_text and not request.document_image_base64:
            raise_policy_http_error(
                422,
                PolicyRejection(
                    code="document_text_or_document_image_base64_required",
                    message="Add contract text or an image before starting document review.",
                    reason="validation_failed",
                    scope="job",
                    metadata={
                        "error_code": "document_text_or_document_image_base64_required",
                    },
                ),
            )
        user_id = enforce_authenticated_user(request.user_id, current_user_id)
        session = resolve_user_session(
            starter=session_starter,
            user_id=user_id,
            module="documents",
            session_id=request.session_id,
        )
        trace_id = request.trace_id or f"trace_{uuid4().hex}"
        result = service.process_contract_review(
            observation_id=request.observation_id or f"obs_{uuid4().hex}",
            user_id=user_id,
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

    @router.post(
        "/api/device-bridge/camera/document-contract-review",
        response_model=SimulationResponse,
    )
    def process_camera_contract_review(
        request: CameraDocumentContractReviewRequest,
        service: Annotated[DocumentSessionService, Depends(get_document_session_service)],
        session_trace_reader: Annotated[GetSessionTrace, Depends(get_session_trace_reader)],
        session_starter: Annotated[StartUserSession, Depends(get_user_session_starter)],
        current_user_id: Annotated[str, Depends(get_current_user_id)],
    ) -> SimulationResponse:
        validate_camera_content_type(request.content_type)
        user_id = enforce_authenticated_user(request.user_id, current_user_id)
        session = resolve_user_session(
            starter=session_starter,
            user_id=user_id,
            module="documents",
            session_id=request.session_id,
        )
        trace_id = request.trace_id or f"trace_{uuid4().hex}"
        result = service.process_contract_review(
            observation_id=request.observation_id or f"obs_{uuid4().hex}",
            user_id=user_id,
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

    @router.get(
        "/api/sessions/{session_id}/document-analyses",
        response_model=list[DocumentAnalysisResponse],
    )
    def list_document_analyses_by_session(
        session_id: str,
        reader: Annotated[
            ListDocumentAnalysesBySession,
            Depends(get_document_analyses_by_session_reader),
        ],
        feedback_reader: Annotated[
            GetDocumentAnalysisFeedback,
            Depends(get_document_analysis_feedback_reader),
        ],
        current_user_id: Annotated[str, Depends(get_current_user_id)],
    ) -> list[DocumentAnalysisResponse]:
        records = reader.execute(session_id=session_id)
        return [
            serialize_document_analysis(
                record,
                feedback=resolve_document_analysis_feedback(record, feedback_reader),
            )
            for record in records
            if record.user_id == current_user_id
        ]

    @router.get(
        "/api/users/{user_id}/sessions/{session_id}/jobs",
        response_model=JobPageResponse,
    )
    def list_session_jobs(
        user_id: str,
        session_id: str,
        lister: Annotated[ListJobsBySession, Depends(get_job_session_lister)],
        policy_rejection_reader: Annotated[
            GetRecentPolicyRejectionForSession,
            Depends(get_recent_policy_rejection_reader),
        ],
        session_reader: Annotated[GetUserSession, Depends(get_user_session_reader)],
        current_user_id: Annotated[str, Depends(get_current_user_id)],
        module: str | None = None,
        status: JobStatus | None = None,
        limit: int = 25,
    ) -> JobPageResponse:
        authenticated_user_id = enforce_authenticated_user(user_id, current_user_id)
        session = session_reader.execute(
            user_id=authenticated_user_id,
            session_id=session_id,
        )
        if session is None or (module is not None and session.module != module):
            raise HTTPException(status_code=404, detail="session_not_found")
        jobs = lister.execute(
            user_id=authenticated_user_id,
            session_id=session_id,
            module=module,
            status=status,
            limit=limit,
        )
        return JobPageResponse(
            user_id=authenticated_user_id,
            session_id=session_id,
            job_count=len(jobs),
            jobs=[serialize_job(job) for job in jobs],
            blocked_reason=serialize_policy_rejection(
                policy_rejection_reader.execute(
                    user_id=authenticated_user_id,
                    session_id=session_id,
                    module=module or "documents",
                )
            ),
        )

    @router.get(
        "/api/document-analyses/{analysis_id}",
        response_model=DocumentAnalysisResponse,
    )
    def get_document_analysis(
        analysis_id: str,
        reader: Annotated[GetDocumentAnalysis, Depends(get_document_analysis_reader)],
        feedback_reader: Annotated[
            GetDocumentAnalysisFeedback,
            Depends(get_document_analysis_feedback_reader),
        ],
        current_user_id: Annotated[str, Depends(get_current_user_id)],
    ) -> DocumentAnalysisResponse:
        record = reader.execute(analysis_id=analysis_id)
        if record is None:
            raise HTTPException(status_code=404, detail="document_analysis_not_found")
        ensure_document_analysis_owned_by_current_user(record, current_user_id)
        return serialize_document_analysis(
            record,
            feedback=resolve_document_analysis_feedback(record, feedback_reader),
        )

    @router.get(
        "/api/users/{user_id}/sessions/{session_id}/feedback-metrics",
        response_model=DocumentFeedbackMetricsResponse,
    )
    def get_document_feedback_metrics(
        user_id: str,
        session_id: str,
        metrics_reader: Annotated[
            GetDocumentFeedbackMetrics,
            Depends(get_document_feedback_metrics_reader),
        ],
        session_reader: Annotated[GetUserSession, Depends(get_user_session_reader)],
        current_user_id: Annotated[str, Depends(get_current_user_id)],
    ) -> DocumentFeedbackMetricsResponse:
        enforce_path_user(user_id, current_user_id)
        session = session_reader.execute(user_id=current_user_id, session_id=session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session_not_found")
        ensure_session_owned_by_current_user(session, current_user_id)
        return serialize_document_feedback_metrics(
            metrics_reader.execute(
                user_id=current_user_id,
                session_id=session_id,
            )
        )

    @router.post(
        "/api/jobs/documents/contract-analysis",
        response_model=JobResponse,
    )
    def enqueue_document_analysis_job(
        request: DocumentAnalysisJobRequest,
        session_starter: Annotated[StartUserSession, Depends(get_user_session_starter)],
        enqueuer=Depends(get_document_job_enqueuer),
        artifact_registrar=Depends(get_document_artifact_registrar),
        artifact_deleter=Depends(get_document_artifact_deleter),
        worker=Depends(get_document_job_worker),
        current_user_id: Annotated[str, Depends(get_current_user_id)] = "",
    ) -> JobResponse:
        if not request.document_text and not request.document_image_base64:
            raise_policy_http_error(
                422,
                PolicyRejection(
                    code="document_text_or_document_image_base64_required",
                    message="Add contract text or an image before queueing analysis.",
                    reason="validation_failed",
                    scope="job",
                    metadata={
                        "error_code": "document_text_or_document_image_base64_required",
                    },
                ),
            )
        user_id = enforce_authenticated_user(request.user_id, current_user_id)
        session = resolve_user_session(
            starter=session_starter,
            user_id=user_id,
            module="documents",
            session_id=request.session_id,
        )
        trace_id = request.trace_id or f"trace_{uuid4().hex}"
        try:
            job = enqueuer.execute(
                user_id=user_id,
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
        except PolicyRejectedError as exc:
            raise_rejected_http_error(policy_status_code_for(exc.rejection), exc)
        if job.status == JobStatus.QUEUED:
            worker.enqueue(job.job_id)
        return serialize_job(job)

    @router.post(
        "/api/uploads/documents/contract-analysis",
        response_model=JobResponse,
    )
    async def upload_document_contract_analysis(
        session_starter: Annotated[StartUserSession, Depends(get_user_session_starter)],
        user_id: Annotated[str, Form(min_length=1)],
        artifact: Annotated[UploadFile, File()],
        enqueuer=Depends(get_document_job_enqueuer),
        artifact_registrar=Depends(get_document_artifact_registrar),
        artifact_deleter=Depends(get_document_artifact_deleter),
        worker=Depends(get_document_job_worker),
        session_id: Annotated[str | None, Form()] = None,
        document_text: Annotated[str | None, Form(min_length=20)] = None,
        confidence: Annotated[float | None, Form(ge=0, le=1)] = 0.92,
        mode: Annotated[AttentionMode, Form()] = AttentionMode.BALANCED,
        recent_category_count: Annotated[int, Form(ge=0)] = 0,
        observation_id: Annotated[str | None, Form()] = None,
        idempotency_key: Annotated[str | None, Form()] = None,
        correlation_id: Annotated[str | None, Form()] = None,
        trace_id: Annotated[str | None, Form()] = None,
        current_user_id: Annotated[str, Depends(get_current_user_id)] = "",
    ) -> JobResponse:
        authenticated_user_id = enforce_authenticated_user(user_id, current_user_id)
        session = resolve_user_session(
            starter=session_starter,
            user_id=authenticated_user_id,
            module="documents",
            session_id=session_id,
        )
        content_type = validate_upload_content_type(artifact.content_type or "")
        payload = await read_upload_bytes(artifact)
        resolved_trace_id = trace_id or f"trace_{uuid4().hex}"
        upload_id = f"upload_{uuid4().hex}"
        original_name = safe_upload_filename(
            artifact.filename,
            fallback=f"{upload_id}{upload_extension_for(content_type)}",
        )
        try:
            artifact_record = artifact_registrar.execute(
                user_id=authenticated_user_id,
                session_id=session.session_id,
                artifact_label=original_name,
                source_type="pwa_multipart_upload",
                content_type=content_type,
                payload=payload,
                metadata={
                    "content_type": content_type,
                    "original_filename": original_name,
                },
                correlation_id=correlation_id,
                trace_id=resolved_trace_id,
            )
        except DocumentArtifactQuotaExceededError as exc:
            rejection = _policy_rejection_for_artifact_quota_error(exc)
            raise_policy_http_error(
                429,
                rejection,
            )

        try:
            job = enqueuer.execute(
                user_id=authenticated_user_id,
                session_id=session.session_id,
                idempotency_key=idempotency_key or f"idem_{upload_id}",
                correlation_id=correlation_id or f"corr_{uuid4().hex}",
                trace_id=resolved_trace_id,
                artifact_label=original_name,
                source_type="pwa_multipart_upload",
                artifact_id=artifact_record.artifact_id,
                document_text=document_text,
                document_image_base64=b64encode(payload).decode("ascii"),
                confidence=confidence,
                mode=mode,
                recent_category_count=recent_category_count,
                observation_id=observation_id or f"obs_{upload_id}",
            )
        except PolicyRejectedError as exc:
            artifact_deleter.execute(
                artifact_id=artifact_record.artifact_id,
                user_id=authenticated_user_id,
                session_id=session.session_id,
                correlation_id=correlation_id,
                trace_id=resolved_trace_id,
            )
            raise_rejected_http_error(policy_status_code_for(exc.rejection), exc)
        except Exception:
            artifact_deleter.execute(
                artifact_id=artifact_record.artifact_id,
                user_id=authenticated_user_id,
                session_id=session.session_id,
                correlation_id=correlation_id,
                trace_id=resolved_trace_id,
            )
            raise
        if job.metadata.get("artifact_id") != artifact_record.artifact_id:
            artifact_deleter.execute(
                artifact_id=artifact_record.artifact_id,
                user_id=authenticated_user_id,
                session_id=session.session_id,
                correlation_id=correlation_id,
                trace_id=resolved_trace_id,
            )
        if job.status == JobStatus.QUEUED:
            worker.enqueue(job.job_id)
        return serialize_job(job)

    @router.delete(
        "/api/document-artifacts/{artifact_id}",
        response_model=DocumentArtifactDeleteResponse,
    )
    def delete_document_artifact(
        artifact_id: str,
        deleter: Annotated[
            DeleteLocalDocumentArtifact,
            Depends(get_document_artifact_deleter),
        ],
        current_user_id: Annotated[str, Depends(get_current_user_id)],
    ) -> DocumentArtifactDeleteResponse:
        try:
            record = deleter.execute(
                artifact_id=artifact_id,
                user_id=current_user_id,
                trace_id=f"trace_{uuid4().hex}",
            )
        except DocumentArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DocumentArtifactOwnershipError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return DocumentArtifactDeleteResponse(
            artifact_id=record.artifact_id,
            session_id=record.session_id,
            status=record.status.value,
            deleted_at=record.deleted_at.isoformat() if record.deleted_at else None,
        )

    @router.get("/api/jobs/{job_id}", response_model=JobResponse)
    def get_job_status(
        job_id: str,
        reader: Annotated[GetJobStatus, Depends(get_job_status_reader)],
        current_user_id: Annotated[str, Depends(get_current_user_id)],
    ) -> JobResponse:
        job = reader.execute(job_id=job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job_not_found")
        ensure_job_owned_by_current_user(job, current_user_id)
        return serialize_job(job)

    @router.post("/api/jobs/{job_id}/status", response_model=JobResponse)
    def advance_job_status(
        job_id: str,
        request: JobTransitionRequest,
        advancer: Annotated[AdvanceDocumentAnalysisJob, Depends(get_document_job_advancer)],
        reader: Annotated[GetJobStatus, Depends(get_job_status_reader)],
        current_user_id: Annotated[str, Depends(get_current_user_id)],
    ) -> JobResponse:
        existing_job = reader.execute(job_id=job_id)
        if existing_job is None:
            raise HTTPException(status_code=404, detail="job_not_found")
        ensure_job_owned_by_current_user(existing_job, current_user_id)
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
        return serialize_job(job)

    @router.get(
        "/api/jobs/{job_id}/result",
        response_model=DocumentAnalysisResponse,
    )
    def get_document_job_result(
        job_id: str,
        job_reader: Annotated[GetJobStatus, Depends(get_job_status_reader)],
        analysis_reader: Annotated[GetDocumentAnalysis, Depends(get_document_analysis_reader)],
        feedback_reader: Annotated[
            GetDocumentAnalysisFeedback,
            Depends(get_document_analysis_feedback_reader),
        ],
        current_user_id: Annotated[str, Depends(get_current_user_id)],
    ) -> DocumentAnalysisResponse:
        job = job_reader.execute(job_id=job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job_not_found")
        ensure_job_owned_by_current_user(job, current_user_id)
        if job.status != JobStatus.SUCCEEDED or not job.result_id:
            raise HTTPException(status_code=409, detail="job_result_not_ready")
        record = analysis_reader.execute(analysis_id=job.result_id)
        if record is None:
            raise HTTPException(status_code=404, detail="job_result_not_found")
        ensure_document_analysis_owned_by_current_user(record, current_user_id)
        return serialize_document_analysis(
            record,
            feedback=resolve_document_analysis_feedback(record, feedback_reader),
        )

    @router.post(
        "/api/document-analyses/{analysis_id}/feedback",
        response_model=DocumentAnalysisFeedbackResponse,
    )
    def record_document_analysis_feedback(
        analysis_id: str,
        request: DocumentAnalysisFeedbackRequest,
        recorder: Annotated[
            RecordDocumentAnalysisFeedback,
            Depends(get_document_analysis_feedback_recorder),
        ],
        current_user_id: Annotated[str, Depends(get_current_user_id)],
    ) -> DocumentAnalysisFeedbackResponse:
        user_id = enforce_authenticated_user(request.user_id, current_user_id)
        result = recorder.execute(
            analysis_id=analysis_id,
            user_id=user_id,
            session_id=request.session_id,
            feedback=request.feedback,
            correlation_id=request.correlation_id or f"corr_{uuid4().hex}",
            trace_id=request.trace_id,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="document_analysis_not_found")
        return DocumentAnalysisFeedbackResponse(
            event_id=result.event_id,
            analysis_id=result.analysis_id,
            feedback=result.feedback.value,
        )

    return router


def _policy_rejection_for_artifact_quota_error(
    error: DocumentArtifactQuotaExceededError,
) -> PolicyRejection:
    if error.code == "session_artifact_storage_limit_exceeded":
        message = "This session reached the local document storage limit."
    else:
        message = "This session reached the upload limit."
    return PolicyRejection(
        code=error.code,
        message=message,
        reason="quota_exceeded",
        scope="session",
        limit=error.limit,
        current=error.current,
        retryable=True,
        metadata={
            "limit_scope": "session",
            "limit_value": error.limit,
            "current_value": error.current,
            "error_code": error.code,
        },
    )
