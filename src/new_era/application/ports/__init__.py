"""Application ports for external systems."""

from new_era.application.ports.document_analysis_job_payload_store import (
    DocumentAnalysisJobPayload,
    DocumentAnalysisJobPayloadStore,
)
from new_era.application.ports.document_analysis_store import DocumentAnalysisStore
from new_era.application.ports.document_artifact_store import DocumentArtifactStore
from new_era.application.ports.device_gateway import (
    DeviceDeliveryError,
    DeviceGateway,
    DeviceGatewayError,
)
from new_era.application.ports.event_store import EventCursor, EventStore
from new_era.application.ports.job_store import JobStore
from new_era.application.ports.local_document_artifact_storage import (
    LocalDocumentArtifactStorage,
    StoredDocumentArtifact,
)
from new_era.application.ports.observation_interpreter import ObservationInterpreter
from new_era.application.ports.ocr_engine import OCREngine
from new_era.application.ports.session_store import SessionCursor, SessionStore

__all__ = [
    "DeviceGateway",
    "DeviceGatewayError",
    "DeviceDeliveryError",
    "DocumentAnalysisJobPayload",
    "DocumentAnalysisJobPayloadStore",
    "DocumentAnalysisStore",
    "DocumentArtifactStore",
    "EventStore",
    "EventCursor",
    "JobStore",
    "LocalDocumentArtifactStorage",
    "ObservationInterpreter",
    "OCREngine",
    "SessionCursor",
    "SessionStore",
    "StoredDocumentArtifact",
]
