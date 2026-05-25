"""Document analysis domain contracts."""

from new_era.domain.documents.analysis import DeterministicContractAnalyzer
from new_era.domain.documents.models import (
    ContractFinding,
    ContractFindingType,
    ContractReviewAnalysis,
    DocumentAnalysisRecord,
    DocumentArtifactRecord,
    DocumentArtifactStatus,
    OCRExtraction,
)

__all__ = [
    "ContractFinding",
    "ContractFindingType",
    "ContractReviewAnalysis",
    "DeterministicContractAnalyzer",
    "DocumentAnalysisRecord",
    "DocumentArtifactRecord",
    "DocumentArtifactStatus",
    "OCRExtraction",
]
