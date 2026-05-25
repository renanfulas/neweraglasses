"""Application use cases."""

from new_era.application.use_cases.document_analysis_jobs import (
    AdvanceDocumentAnalysisJob,
    DocumentAnalysisJobTimedOut,
    EnqueueDocumentAnalysisJob,
    GetJobStatus,
    ListJobsBySession,
    RunDocumentAnalysisJob,
)
from new_era.application.use_cases.document_artifact_lifecycle import (
    DeleteLocalDocumentArtifact,
    DocumentArtifactNotFoundError,
    DocumentArtifactOwnershipError,
    DocumentArtifactQuotaExceededError,
    EnforceSessionArtifactQuota,
    ExpireDocumentArtifact,
    RegisterLocalDocumentArtifact,
    SessionArtifactQuota,
)
from new_era.application.use_cases.get_document_analysis import (
    GetDocumentAnalysis,
    ListDocumentAnalysesBySession,
)
from new_era.application.use_cases.get_document_feedback_metrics import (
    DocumentFeedbackMetricsReadModel,
    GetDocumentFeedbackMetrics,
)
from new_era.application.use_cases.get_recent_policy_rejection import (
    GetRecentPolicyRejectionForSession,
)
from new_era.application.use_cases.deliver_lens_command import DeliverLensCommand
from new_era.application.use_cases.evaluate_alert_candidate import EvaluateAlertCandidate
from new_era.application.use_cases.get_session_trace import (
    GetSessionTrace,
    SessionTraceEntry,
    SessionTraceReadModel,
)
from new_era.application.use_cases.process_observation import (
    ObservationProcessingResult,
    ProcessObservation,
)
from new_era.application.use_cases.process_alert_candidate import (
    AlertProcessingOutcome,
    AlertProcessingResult,
    ProcessAlertCandidate,
)
from new_era.application.use_cases.policy_rejection import (
    PolicyRejectedError,
    PolicyRejection,
)
from new_era.application.use_cases.record_lens_feedback import (
    LensFeedbackResult,
    LensFeedbackValue,
    RecordLensFeedback,
)
from new_era.application.use_cases.record_document_analysis_feedback import (
    DocumentAnalysisFeedbackResult,
    DocumentAnalysisFeedbackValue,
    GetDocumentAnalysisFeedback,
    RecordDocumentAnalysisFeedback,
)
from new_era.application.use_cases.user_sessions import (
    GetUserSession,
    ListUserSessions,
    SessionOwnershipError,
    StartUserSession,
    UserSessionPageReadModel,
    UserSessionReadModel,
)

__all__ = [
    "AlertProcessingOutcome",
    "AlertProcessingResult",
    "AdvanceDocumentAnalysisJob",
    "DocumentAnalysisJobTimedOut",
    "DeliverLensCommand",
    "DeleteLocalDocumentArtifact",
    "DocumentAnalysisFeedbackResult",
    "DocumentAnalysisFeedbackValue",
    "EnqueueDocumentAnalysisJob",
    "EnforceSessionArtifactQuota",
    "EvaluateAlertCandidate",
    "ExpireDocumentArtifact",
    "GetDocumentAnalysis",
    "GetDocumentFeedbackMetrics",
    "GetDocumentAnalysisFeedback",
    "GetJobStatus",
    "GetRecentPolicyRejectionForSession",
    "GetSessionTrace",
    "GetUserSession",
    "LensFeedbackResult",
    "LensFeedbackValue",
    "ListJobsBySession",
    "ListUserSessions",
    "ListDocumentAnalysesBySession",
    "ObservationProcessingResult",
    "PolicyRejectedError",
    "PolicyRejection",
    "ProcessObservation",
    "RecordDocumentAnalysisFeedback",
    "ProcessAlertCandidate",
    "RegisterLocalDocumentArtifact",
    "RecordLensFeedback",
    "RunDocumentAnalysisJob",
    "SessionArtifactQuota",
    "SessionOwnershipError",
    "SessionTraceEntry",
    "SessionTraceReadModel",
    "StartUserSession",
    "UserSessionPageReadModel",
    "UserSessionReadModel",
    "DocumentFeedbackMetricsReadModel",
    "DocumentArtifactNotFoundError",
    "DocumentArtifactOwnershipError",
    "DocumentArtifactQuotaExceededError",
]
