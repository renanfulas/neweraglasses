from __future__ import annotations

from dataclasses import dataclass

from new_era.application.ports import (
    DeviceGateway,
    DocumentAnalysisStore,
    EventStore,
    OCREngine,
    ObservationInterpreter,
)
from new_era.application.use_cases import ObservationProcessingResult, ProcessObservation
from new_era.domain.attention import AttentionMode
from new_era.domain.documents import (
    ContractReviewAnalysis,
    DeterministicContractAnalyzer,
    DocumentAnalysisRecord,
)
from new_era.domain.observations import Observation, ObservationKind
from new_era.infrastructure.device import BrowserSimulationAdapter
from new_era.infrastructure.documents import InMemoryDocumentAnalysisStore
from new_era.infrastructure.events import InMemoryEventStore
from new_era.infrastructure.observations import SimpleSimulationObservationAdapter
from new_era.infrastructure.ocr import RapidOCRAdapter


@dataclass(frozen=True, slots=True)
class DocumentContractReviewResult:
    processing_result: ObservationProcessingResult
    analysis: ContractReviewAnalysis
    analysis_record: DocumentAnalysisRecord

    @property
    def outcome(self):
        return self.processing_result.outcome

    @property
    def candidate_created(self) -> bool:
        return self.processing_result.candidate_created

    @property
    def alert_result(self):
        return self.processing_result.alert_result


@dataclass(frozen=True, slots=True)
class DocumentSessionService:
    observation_processor: ProcessObservation
    event_store: EventStore
    device_gateway: DeviceGateway
    contract_analyzer: DeterministicContractAnalyzer
    ocr_engine: OCREngine
    analysis_store: DocumentAnalysisStore

    def process_contract_review(
        self,
        *,
        observation_id: str,
        user_id: str,
        session_id: str,
        document_text: str | None,
        document_image_base64: str | None,
        confidence: float | None,
        mode: AttentionMode,
        recent_category_count: int,
        correlation_id: str,
        trace_id: str,
    ) -> DocumentContractReviewResult:
        ocr_extraction = None
        extracted_text = (document_text or "").strip()
        source_confidence = float(confidence if confidence is not None else 0.0)

        if document_image_base64:
            ocr_extraction = self.ocr_engine.extract_text(image_base64=document_image_base64)
            extracted_text = ocr_extraction.text
            source_confidence = ocr_extraction.confidence
        elif extracted_text:
            source_confidence = float(confidence if confidence is not None else 0.92)

        analysis = self.contract_analyzer.analyze(
            document_text=extracted_text,
            source_confidence=source_confidence,
        )
        source_type = "image_ocr" if document_image_base64 else "plain_text"
        analysis_record = DocumentAnalysisRecord(
            user_id=user_id,
            session_id=session_id,
            observation_id=observation_id,
            trace_id=trace_id,
            source_type=source_type,
            analysis=analysis,
        )
        self.analysis_store.save(analysis_record)
        observation = Observation(
            observation_id=observation_id,
            user_id=user_id,
            session_id=session_id,
            module="documents",
            kind=ObservationKind.DOCUMENT_CONTRACT_REVIEW,
            summary="Contract review requested from PWA simulation",
            metadata={
                "document_analysis": analysis.to_dict(),
                "analysis_id": analysis_record.analysis_id,
                "source_type": source_type,
                "ocr_engine": ocr_extraction.engine_name if ocr_extraction else None,
            },
        )
        processing_result = self.observation_processor.execute(
            observation=observation,
            mode=mode,
            recent_category_count=recent_category_count,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )
        return DocumentContractReviewResult(
            processing_result=processing_result,
            analysis=analysis,
            analysis_record=analysis_record,
        )

    @classmethod
    def build_simulation(
        cls,
        *,
        observation_processor: ProcessObservation,
        event_store: EventStore,
        device_gateway: DeviceGateway,
        contract_analyzer: DeterministicContractAnalyzer,
        ocr_engine: OCREngine,
        analysis_store: DocumentAnalysisStore,
    ) -> "DocumentSessionService":
        return cls(
            observation_processor=observation_processor,
            event_store=event_store,
            device_gateway=device_gateway,
            contract_analyzer=contract_analyzer,
            ocr_engine=ocr_engine,
            analysis_store=analysis_store,
        )

    @classmethod
    def build_default_simulation(cls) -> "DocumentSessionService":
        from new_era.application.use_cases import (
            DeliverLensCommand,
            EvaluateAlertCandidate,
            ProcessAlertCandidate,
        )
        from new_era.domain.attention import AttentionPolicy

        event_store = InMemoryEventStore()
        device_gateway = BrowserSimulationAdapter()
        observation_interpreter: ObservationInterpreter = SimpleSimulationObservationAdapter()
        contract_analyzer = DeterministicContractAnalyzer()
        ocr_engine: OCREngine = RapidOCRAdapter()
        analysis_store: DocumentAnalysisStore = InMemoryDocumentAnalysisStore()
        observation_processor = ProcessObservation(
            observation_interpreter=observation_interpreter,
            alert_processor=ProcessAlertCandidate(
                evaluator=EvaluateAlertCandidate(
                    attention_policy=AttentionPolicy(),
                    event_store=event_store,
                ),
                delivery=DeliverLensCommand(
                    device_gateway=device_gateway,
                    event_store=event_store,
                ),
            ),
            event_store=event_store,
        )
        return cls.build_simulation(
            observation_processor=observation_processor,
            event_store=event_store,
            device_gateway=device_gateway,
            contract_analyzer=contract_analyzer,
            ocr_engine=ocr_engine,
            analysis_store=analysis_store,
        )
