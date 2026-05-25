from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class OCRExtraction:
    text: str
    confidence: float
    engine_name: str
    line_count: int = 0


@dataclass(frozen=True, slots=True)
class DocumentAnalysisRecord:
    user_id: str
    session_id: str
    observation_id: str
    trace_id: str
    source_type: str
    analysis: dict[str, object]
    analysis_id: str = field(default_factory=lambda: f"analysis_{uuid4().hex}")
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        return {
            "analysis_id": self.analysis_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "observation_id": self.observation_id,
            "trace_id": self.trace_id,
            "source_type": self.source_type,
            "created_at": self.created_at.isoformat(),
            "analysis": dict(self.analysis),
        }
