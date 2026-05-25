from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath

from fastapi import HTTPException, UploadFile

from new_era.application.use_cases import GetDocumentAnalysisFeedback, GetSessionTrace, StartUserSession
from new_era.domain.documents import DocumentAnalysisRecord
from new_era.domain.events import EventType
from new_era.domain.jobs import JobRecord
from new_era.domain.sessions import UserSession

MAX_DOCUMENT_UPLOAD_BYTES = 7_500_000
SUPPORTED_DOCUMENT_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def enforce_authenticated_user(
    request_user_id: str,
    current_user_id: str,
) -> str:
    if request_user_id != current_user_id:
        raise HTTPException(status_code=403, detail="authenticated_user_mismatch")
    return current_user_id


def enforce_path_user(
    path_user_id: str,
    current_user_id: str,
) -> str:
    if path_user_id != current_user_id:
        raise HTTPException(status_code=403, detail="authenticated_user_mismatch")
    return current_user_id


def ensure_session_owned_by_current_user(
    session: UserSession,
    current_user_id: str,
) -> UserSession:
    if session.user_id != current_user_id:
        raise HTTPException(status_code=404, detail="session_not_found")
    return session


def ensure_job_owned_by_current_user(job: JobRecord, current_user_id: str) -> JobRecord:
    if job.user_id != current_user_id:
        raise HTTPException(status_code=404, detail="job_not_found")
    return job


def ensure_document_analysis_owned_by_current_user(
    record: DocumentAnalysisRecord,
    current_user_id: str,
) -> DocumentAnalysisRecord:
    if record.user_id != current_user_id:
        raise HTTPException(status_code=404, detail="document_analysis_not_found")
    return record


def resolve_document_analysis_feedback(
    record: DocumentAnalysisRecord,
    feedback_reader: GetDocumentAnalysisFeedback,
) -> str | None:
    feedback = feedback_reader.execute(
        analysis_id=record.analysis_id,
        user_id=record.user_id,
        session_id=record.session_id,
    )
    return feedback.value if feedback else None


def resolve_user_session(
    *,
    starter: StartUserSession,
    user_id: str,
    module: str,
    session_id: str | None,
) -> UserSession:
    from new_era.application.use_cases import SessionOwnershipError

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
    if normalized not in SUPPORTED_DOCUMENT_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="unsupported_camera_content_type")


def validate_upload_content_type(content_type: str) -> str:
    normalized = content_type.lower().split(";", 1)[0].strip()
    if normalized not in SUPPORTED_DOCUMENT_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="unsupported_upload_content_type")
    return normalized


def safe_upload_filename(filename: str | None, *, fallback: str) -> str:
    raw_name = (filename or fallback).strip() or fallback
    safe_name = "".join(
        character if character.isalnum() or character in "._-" else "-"
        for character in raw_name
    ).strip(".-")
    return safe_name or fallback


def upload_extension_for(content_type: str) -> str:
    if content_type == "image/png":
        return ".png"
    if content_type == "image/webp":
        return ".webp"
    return ".jpg"


async def read_upload_bytes(upload: UploadFile) -> bytes:
    payload = await upload.read(MAX_DOCUMENT_UPLOAD_BYTES + 1)
    if not payload:
        raise HTTPException(status_code=422, detail="upload_file_empty")
    if len(payload) > MAX_DOCUMENT_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="upload_file_too_large")
    return payload


def build_simulation_response(
    *,
    result,
    session_trace_reader: GetSessionTrace,
    session_id: str,
    delivered_commands: list[object],
    trace_id: str,
    analysis: dict[str, object] | None = None,
    analysis_id: str | None = None,
):
    from new_era.infrastructure.http.schemas import SimulationResponse

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
