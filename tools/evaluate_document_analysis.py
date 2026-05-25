from __future__ import annotations

import argparse
import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from new_era.domain.documents import DeterministicContractAnalyzer
from new_era.infrastructure.ocr import RapidOCRAdapter


DEFAULT_FIXTURES_DIR = (
    Path(__file__).resolve().parents[1] / "evals" / "document_analysis" / "fixtures"
)


@dataclass(frozen=True, slots=True)
class FixtureInput:
    document_text: str | None
    document_image_base64: str | None
    document_image_path: str | None
    source_confidence: float | None


@dataclass(frozen=True, slots=True)
class FixtureExpectation:
    has_findings: bool | None = None
    finding_types: tuple[str, ...] = ()
    finding_count: int | None = None
    min_review_confidence: float | None = None
    max_review_confidence: float | None = None
    min_source_confidence: float | None = None
    summary_title: str | None = None
    parsing_notes: tuple[str, ...] = ()
    extracted_text_contains: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvaluationFixture:
    fixture_id: str
    name: str
    description: str
    input: FixtureInput
    expected: FixtureExpectation


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    fixture_id: str
    name: str
    passed: bool
    source_type: str
    failures: tuple[str, ...]
    analysis: dict[str, Any]
    ocr: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "name": self.name,
            "passed": self.passed,
            "source_type": self.source_type,
            "failures": list(self.failures),
            "analysis": self.analysis,
            "ocr": self.ocr,
        }


def load_fixture(path: Path) -> EvaluationFixture:
    payload = json.loads(path.read_text(encoding="utf-8"))
    input_payload = payload.get("input", {})
    expected_payload = payload.get("expected", {})
    return EvaluationFixture(
        fixture_id=str(payload["fixture_id"]),
        name=str(payload["name"]),
        description=str(payload.get("description", "")),
        input=FixtureInput(
            document_text=_optional_string(input_payload.get("document_text")),
            document_image_base64=_optional_string(input_payload.get("document_image_base64")),
            document_image_path=_optional_string(input_payload.get("document_image_path")),
            source_confidence=_optional_float(input_payload.get("source_confidence")),
        ),
        expected=FixtureExpectation(
            has_findings=_optional_bool(expected_payload.get("has_findings")),
            finding_types=_tuple_of_strings(expected_payload.get("finding_types")),
            finding_count=_optional_int(expected_payload.get("finding_count")),
            min_review_confidence=_optional_float(expected_payload.get("min_review_confidence")),
            max_review_confidence=_optional_float(expected_payload.get("max_review_confidence")),
            min_source_confidence=_optional_float(expected_payload.get("min_source_confidence")),
            summary_title=_optional_string(expected_payload.get("summary_title")),
            parsing_notes=_tuple_of_strings(expected_payload.get("parsing_notes")),
            extracted_text_contains=_tuple_of_strings(
                expected_payload.get("extracted_text_contains")
            ),
        ),
    )


def discover_fixture_paths(fixtures_dir: Path) -> list[Path]:
    return sorted(path for path in fixtures_dir.glob("*.json") if path.is_file())


def evaluate_fixture(
    fixture: EvaluationFixture,
    *,
    analyzer: DeterministicContractAnalyzer | None = None,
    ocr_engine: RapidOCRAdapter | None = None,
) -> EvaluationResult:
    analyzer = analyzer or DeterministicContractAnalyzer()
    failures: list[str] = []
    ocr_payload: dict[str, Any] | None = None
    extracted_text = (fixture.input.document_text or "").strip()
    source_confidence = float(fixture.input.source_confidence or 0.0)
    source_type = "plain_text"

    image_base64 = fixture.input.document_image_base64
    if fixture.input.document_image_path:
        image_bytes = Path(fixture.input.document_image_path).read_bytes()
        image_base64 = base64.b64encode(image_bytes).decode("ascii")

    if image_base64:
        engine = ocr_engine or RapidOCRAdapter()
        extraction = engine.extract_text(image_base64=image_base64)
        ocr_payload = extraction.to_dict()
        extracted_text = extraction.text
        source_confidence = extraction.confidence
        source_type = "image_ocr"
    elif extracted_text:
        source_confidence = float(
            fixture.input.source_confidence if fixture.input.source_confidence is not None else 0.92
        )

    analysis = analyzer.analyze(
        document_text=extracted_text,
        source_confidence=source_confidence,
    )
    analysis_payload = analysis.to_dict()
    finding_types = tuple(finding["finding_type"] for finding in analysis_payload["findings"])

    expected = fixture.expected
    if expected.has_findings is not None and analysis.has_findings != expected.has_findings:
        failures.append(
            f"expected has_findings={expected.has_findings}, got {analysis.has_findings}"
        )
    if expected.finding_count is not None and len(analysis.findings) != expected.finding_count:
        failures.append(
            f"expected finding_count={expected.finding_count}, got {len(analysis.findings)}"
        )
    if expected.finding_types and finding_types != expected.finding_types:
        failures.append(
            f"expected finding_types={list(expected.finding_types)}, got {list(finding_types)}"
        )
    if (
        expected.min_review_confidence is not None
        and analysis.review_confidence < expected.min_review_confidence
    ):
        failures.append(
            "expected review_confidence >= "
            f"{expected.min_review_confidence}, got {analysis.review_confidence}"
        )
    if (
        expected.max_review_confidence is not None
        and analysis.review_confidence > expected.max_review_confidence
    ):
        failures.append(
            "expected review_confidence <= "
            f"{expected.max_review_confidence}, got {analysis.review_confidence}"
        )
    if (
        expected.min_source_confidence is not None
        and analysis.source_confidence < expected.min_source_confidence
    ):
        failures.append(
            "expected source_confidence >= "
            f"{expected.min_source_confidence}, got {analysis.source_confidence}"
        )
    if expected.summary_title and analysis.summary_title != expected.summary_title:
        failures.append(
            f"expected summary_title={expected.summary_title!r}, got {analysis.summary_title!r}"
        )
    missing_notes = [note for note in expected.parsing_notes if note not in analysis.parsing_notes]
    if missing_notes:
        failures.append(f"missing parsing_notes={missing_notes}")
    missing_snippets = [
        snippet for snippet in expected.extracted_text_contains if snippet not in analysis.extracted_text
    ]
    if missing_snippets:
        failures.append(f"missing extracted_text_contains={missing_snippets}")

    return EvaluationResult(
        fixture_id=fixture.fixture_id,
        name=fixture.name,
        passed=not failures,
        source_type=source_type,
        failures=tuple(failures),
        analysis=analysis_payload,
        ocr=ocr_payload,
    )


def evaluate_fixtures(paths: list[Path]) -> list[EvaluationResult]:
    fixtures = [load_fixture(path) for path in paths]
    return [evaluate_fixture(fixture) for fixture in fixtures]


def build_summary(results: list[EvaluationResult]) -> dict[str, Any]:
    passed_count = sum(1 for result in results if result.passed)
    return {
        "passed": passed_count == len(results),
        "total": len(results),
        "passed_count": passed_count,
        "failed_count": len(results) - passed_count,
        "results": [result.to_dict() for result in results],
    }


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _tuple_of_strings(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(str(item) for item in value)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local OCR/document analysis eval fixtures without the HTTP app."
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=DEFAULT_FIXTURES_DIR,
        help="Directory containing JSON fixtures.",
    )
    parser.add_argument(
        "--fixture",
        action="append",
        type=Path,
        default=[],
        help="Specific fixture file(s) to run. Can be passed multiple times.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full evaluation summary as JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    fixture_paths = args.fixture or discover_fixture_paths(args.fixtures_dir)
    if not fixture_paths:
        raise SystemExit("no fixture files found")

    results = evaluate_fixtures(fixture_paths)
    summary = build_summary(results)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            "document_analysis_eval "
            f"passed={summary['passed_count']}/{summary['total']} failed={summary['failed_count']}"
        )
        for result in results:
            status = "PASS" if result.passed else "FAIL"
            print(f"- {status} {result.fixture_id} ({result.source_type})")
            for failure in result.failures:
                print(f"  * {failure}")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
