from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from new_era.application.use_cases import (
    DocumentAnalysisFeedbackValue,
    DocumentFeedbackMetricsReadModel,
    LensFeedbackValue,
)
from new_era.domain.attention import AttentionMode
from new_era.domain.documents import DocumentAnalysisRecord
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
    document_image_base64: str | None = Field(default=None, max_length=10_500_000)
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
    image_base64: str = Field(min_length=1, max_length=10_500_000)
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
    document_image_base64: str | None = Field(default=None, max_length=10_500_000)
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


class JobPageResponse(BaseModel):
    user_id: str
    session_id: str
    job_count: int
    jobs: list[JobResponse]


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
    artifact_id: str | None = None
    created_at: str
    analysis: dict[str, object]
    feedback: str | None = None


class DocumentAnalysisFeedbackRequest(BaseModel):
    user_id: str
    session_id: str
    feedback: DocumentAnalysisFeedbackValue
    correlation_id: str | None = None
    trace_id: str | None = None


class DocumentAnalysisFeedbackResponse(BaseModel):
    event_id: str
    analysis_id: str
    feedback: str


class DocumentArtifactDeleteResponse(BaseModel):
    artifact_id: str
    session_id: str
    status: str
    deleted_at: str | None


class FeedbackAggregateResponse(BaseModel):
    analysis_count: int
    feedback_count: int
    useful_feedback_count: int
    not_useful_feedback_count: int
    feedback_rate: float | None = None
    useful_feedback_rate: float | None = None


class FindingTypeFeedbackAggregateResponse(FeedbackAggregateResponse):
    finding_type: str


class DocumentFeedbackMetricsResponse(BaseModel):
    user_id: str
    session_id: str
    aggregate: FeedbackAggregateResponse
    by_finding_type: list[FindingTypeFeedbackAggregateResponse]


def serialize_job(job: JobRecord) -> JobResponse:
    return JobResponse(**job.to_dict())


def serialize_document_analysis(
    record: DocumentAnalysisRecord,
    *,
    feedback: str | None = None,
) -> DocumentAnalysisResponse:
    return DocumentAnalysisResponse(**record.to_dict(), feedback=feedback)


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


def serialize_user_session(session: UserSession) -> UserSessionResponse:
    return UserSessionResponse(**session.to_dict())


def serialize_document_feedback_metrics(
    metrics: DocumentFeedbackMetricsReadModel,
) -> DocumentFeedbackMetricsResponse:
    return DocumentFeedbackMetricsResponse(**metrics.to_dict())
