from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from new_era.application.services import DocumentSessionService, GrocerySessionService
from new_era.domain.attention import AttentionMode
from new_era.domain.events import Event, EventType


class HealthResponse(BaseModel):
    status: str


class GroceryMissingItemRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_id: str
    session_id: str
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
    session_id: str
    document_text: str = Field(min_length=20)
    confidence: float = Field(ge=0, le=1, default=0.92)
    mode: AttentionMode = AttentionMode.BALANCED
    recent_category_count: int = Field(ge=0, default=0)
    observation_id: str | None = None
    correlation_id: str | None = None
    trace_id: str | None = None


class SimulationResponse(BaseModel):
    outcome: str
    candidate_created: bool
    command: dict[str, object] | None
    event_count: int
    delivered_commands_count: int
    session_trace: list[dict[str, object]]


def build_trace_title(event: Event) -> str:
    if event.event_type == EventType.OBSERVATION_CREATED:
        return "Observation captured"
    if event.event_type == EventType.ALERT_CANDIDATE_CREATED:
        return "Alert candidate created"
    if event.event_type == EventType.ALERT_SHOWN:
        return "Attention policy allowed display"
    if event.event_type == EventType.ALERT_SUPPRESSED:
        return "Attention policy suppressed alert"
    if event.event_type == EventType.LENS_COMMAND_DELIVERED:
        return "Lens command delivered"
    if event.event_type == EventType.DEVICE_CAPABILITY_MISSING:
        return "Device capability missing"
    return event.event_type.value.replace("_", " ").title()


def build_trace_detail(event: Event) -> str:
    metadata = event.metadata
    if event.event_type == EventType.OBSERVATION_CREATED:
        return str(metadata.get("summary", "Observation received."))
    if event.event_type == EventType.ALERT_CANDIDATE_CREATED:
        priority = str(metadata.get("priority", "unknown")).replace("_", " ")
        confidence = metadata.get("confidence")
        return (
            f"{metadata.get('alert_type', 'alert')} candidate "
            f"with {priority} priority at confidence {confidence}."
        )
    if event.event_type in (EventType.ALERT_SHOWN, EventType.ALERT_SUPPRESSED):
        return str(metadata.get("reason", "No decision reason recorded."))
    if event.event_type == EventType.LENS_COMMAND_DELIVERED:
        return f"Rendered by {metadata.get('adapter_name', 'device adapter')}."
    if event.event_type == EventType.DEVICE_CAPABILITY_MISSING:
        return (
            f"Missing {metadata.get('missing_capability', 'required capability')} on "
            f"{metadata.get('adapter_name', 'device adapter')}."
        )
    return "Event recorded."


def build_trace_step(event_type: EventType) -> str:
    if event_type == EventType.OBSERVATION_CREATED:
        return "observation"
    if event_type == EventType.ALERT_CANDIDATE_CREATED:
        return "candidate"
    if event_type in (EventType.ALERT_SHOWN, EventType.ALERT_SUPPRESSED):
        return "decision"
    if event_type in (EventType.LENS_COMMAND_DELIVERED, EventType.DEVICE_CAPABILITY_MISSING):
        return "delivery"
    return "system"


def serialize_session_trace(events: list[Event], trace_id: str) -> list[dict[str, object]]:
    trace_events = [event for event in events if event.trace_id == trace_id]
    serialized_trace: list[dict[str, object]] = []

    for event in trace_events:
        serialized_trace.append(
            {
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "step": build_trace_step(event.event_type),
                "title": build_trace_title(event),
                "detail": build_trace_detail(event),
                "created_at": event.created_at.isoformat(),
            }
        )

    return serialized_trace


def get_grocery_session_service() -> GrocerySessionService:
    return GrocerySessionService.build_default_simulation()


def get_document_session_service() -> DocumentSessionService:
    return DocumentSessionService.build_default_simulation()


def build_simulation_response(
    *,
    result,
    event_store_events: list[Event],
    delivered_commands: list[object],
    trace_id: str,
) -> SimulationResponse:
    return SimulationResponse(
        outcome=result.outcome.value,
        candidate_created=result.candidate_created,
        command=result.alert_result.command.to_dict()
        if result.alert_result and result.alert_result.command
        else None,
        event_count=len(event_store_events),
        delivered_commands_count=len(delivered_commands),
        session_trace=serialize_session_trace(event_store_events, trace_id),
    )


def create_app() -> FastAPI:
    app = FastAPI(title="New Era Glasses API", version="0.1.0")
    static_dir = Path(__file__).with_name("static")

    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

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
    ) -> SimulationResponse:
        trace_id = request.trace_id or f"trace_{uuid4().hex}"
        result = service.process_missing_item(
            observation_id=request.observation_id or f"obs_{uuid4().hex}",
            user_id=request.user_id,
            session_id=request.session_id,
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
            event_store_events=service.event_store.events,
            delivered_commands=delivered_commands,
            trace_id=trace_id,
        )

    @app.post(
        "/api/simulations/documents/contract-review",
        response_model=SimulationResponse,
    )
    def simulate_contract_review(
        request: DocumentContractReviewRequest,
        service: Annotated[DocumentSessionService, Depends(get_document_session_service)],
    ) -> SimulationResponse:
        trace_id = request.trace_id or f"trace_{uuid4().hex}"
        result = service.process_contract_review(
            observation_id=request.observation_id or f"obs_{uuid4().hex}",
            user_id=request.user_id,
            session_id=request.session_id,
            document_text=request.document_text,
            confidence=request.confidence,
            mode=request.mode,
            recent_category_count=request.recent_category_count,
            correlation_id=request.correlation_id or f"corr_{uuid4().hex}",
            trace_id=trace_id,
        )
        delivered_commands = getattr(service.device_gateway, "delivered_commands", [])

        return build_simulation_response(
            result=result,
            event_store_events=service.event_store.events,
            delivered_commands=delivered_commands,
            trace_id=trace_id,
        )

    return app
