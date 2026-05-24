"""Application ports for external systems."""

from new_era.application.ports.document_analysis_job_payload_store import (
    DocumentAnalysisJobPayload,
    DocumentAnalysisJobPayloadStore,
)
from new_era.application.ports.document_analysis_store import DocumentAnalysisStore
from new_era.application.ports.device_gateway import DeviceGateway
from new_era.application.ports.event_store import EventStore
from new_era.application.ports.job_store import JobStore
from new_era.application.ports.observation_interpreter import ObservationInterpreter
from new_era.application.ports.ocr_engine import OCREngine

__all__ = [
    "DeviceGateway",
    "DocumentAnalysisJobPayload",
    "DocumentAnalysisJobPayloadStore",
    "DocumentAnalysisStore",
    "EventStore",
    "JobStore",
    "ObservationInterpreter",
    "OCREngine",
]
