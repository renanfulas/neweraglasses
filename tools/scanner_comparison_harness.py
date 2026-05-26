from __future__ import annotations

import argparse
import io
import json
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from new_era.infrastructure.http.app import create_app


DEFAULT_CONTRACT_PATH = ROOT_DIR / "docs" / "examples" / "sample-contract-mvp.txt"


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    name: str
    route: str
    status: str
    analysis_id: str
    job_id: str | None
    job_source_type: str | None
    analysis_source_type: str
    artifact_id: str | None
    summary_title: str
    review_confidence: float
    source_confidence: float
    finding_types: tuple[str, ...]
    event_count: int | None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "route": self.route,
            "status": self.status,
            "analysis_id": self.analysis_id,
            "job_id": self.job_id,
            "job_source_type": self.job_source_type,
            "analysis_source_type": self.analysis_source_type,
            "artifact_id": self.artifact_id,
            "summary_title": self.summary_title,
            "review_confidence": self.review_confidence,
            "source_confidence": self.source_confidence,
            "finding_types": list(self.finding_types),
            "event_count": self.event_count,
        }


def ensure_contract_fixture(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "CONTRATO DE PRESTACAO DE SERVICOS",
                "",
                "1. VIGENCIA",
                "O contrato tera vigencia de 12 meses e renovacao automatica.",
                "",
                "2. CANCELAMENTO",
                "Cancelamento antecipado tera multa de cancelamento.",
                "",
                "3. PAGAMENTO",
                "Atraso no pagamento tera juros de 1% ao mes.",
            ]
        ),
        encoding="utf-8",
    )


def render_contract_png(contract_text: str) -> bytes:
    font = ImageFont.load_default(size=28)
    title_font = ImageFont.load_default(size=34)
    line_height = 38
    margin = 48
    wrapped_lines: list[str] = []
    for raw_line in contract_text.splitlines():
        if not raw_line.strip():
            wrapped_lines.append("")
            continue
        wrapped_lines.extend(textwrap.wrap(raw_line, width=78) or [""])

    width = 1800
    height = max(900, margin * 2 + (len(wrapped_lines) + 2) * line_height)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((margin, margin), "Generated contract capture", fill="black", font=title_font)

    y = margin + line_height + 16
    for line in wrapped_lines:
        draw.text((margin, y), line, fill="black", font=font)
        y += line_height

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def run_direct_contract_text(
    client: TestClient,
    *,
    user_id: str,
    session_id: str,
    contract_text: str,
) -> ScenarioResult:
    trace_id = "trace_direct_contract_text"
    response = client.post(
        "/api/simulations/documents/contract-review",
        json={
            "user_id": user_id,
            "session_id": session_id,
            "document_text": contract_text,
            "confidence": 0.92,
            "mode": "balanced",
            "recent_category_count": 0,
            "observation_id": "obs_direct_contract_text",
            "correlation_id": "corr_direct_contract_text",
            "trace_id": trace_id,
        },
    )
    require_ok(response, "direct text simulation")
    payload = response.json()
    analysis_record = fetch_analysis(client, payload["analysis_id"])
    return build_result(
        name="direct_contract_text",
        route="/api/simulations/documents/contract-review",
        status=payload["outcome"],
        analysis_record=analysis_record,
        job=None,
        event_count=payload["event_count"],
    )


def run_upload_ocr(
    client: TestClient,
    app: Any,
    *,
    user_id: str,
    session_id: str,
    contract_text: str,
) -> ScenarioResult:
    image_bytes = render_contract_png(contract_text)
    response = client.post(
        "/api/uploads/documents/contract-analysis",
        data={
            "user_id": user_id,
            "session_id": session_id,
            "idempotency_key": "idem_upload_ocr_contract",
            "mode": "balanced",
            "recent_category_count": "0",
            "observation_id": "obs_upload_ocr_contract",
            "correlation_id": "corr_upload_ocr_contract",
            "trace_id": "trace_upload_ocr_contract",
        },
        files={
            "artifact": ("sample-contract-mvp.png", image_bytes, "image/png"),
        },
    )
    require_ok(response, "multipart OCR upload")
    job = wait_for_job_result(client, app, response.json(), "multipart OCR upload")
    analysis_record = fetch_job_result(client, job["job_id"])
    return build_result(
        name="upload_generated_image_ocr",
        route="/api/uploads/documents/contract-analysis",
        status=job["status"],
        analysis_record=analysis_record,
        job=job,
        event_count=None,
    )


def run_scanner_text(
    client: TestClient,
    app: Any,
    *,
    user_id: str,
    session_id: str,
    contract_text: str,
) -> ScenarioResult:
    response = client.post(
        "/api/jobs/documents/contract-analysis",
        json={
            "user_id": user_id,
            "session_id": session_id,
            "artifact_label": "mobile-text-scanner-contract.txt",
            "source_type": "mobile_text_scanner",
            "idempotency_key": "idem_mobile_text_scanner_contract",
            "document_text": contract_text,
            "mode": "balanced",
            "recent_category_count": 0,
            "observation_id": "obs_mobile_text_scanner_contract",
            "correlation_id": "corr_mobile_text_scanner_contract",
            "trace_id": "trace_mobile_text_scanner_contract",
        },
    )
    require_ok(response, "mobile_text_scanner job")
    job = wait_for_job_result(client, app, response.json(), "mobile_text_scanner job")
    analysis_record = fetch_job_result(client, job["job_id"])
    return build_result(
        name="simulated_mobile_text_scanner",
        route="/api/jobs/documents/contract-analysis",
        status=job["status"],
        analysis_record=analysis_record,
        job=job,
        event_count=None,
    )


def wait_for_job_result(
    client: TestClient,
    app: Any,
    job: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    if not app.state.runtime.document_job_worker.wait_until_idle(timeout_seconds=60):
        raise RuntimeError(f"{label}: document job worker did not become idle")
    status_response = client.get(f"/api/jobs/{job['job_id']}")
    require_ok(status_response, f"{label} status")
    refreshed_job = status_response.json()
    if refreshed_job["status"] != "succeeded":
        raise RuntimeError(
            f"{label}: expected succeeded, got {refreshed_job['status']} "
            f"({refreshed_job.get('error_code')}: {refreshed_job.get('error_message')})"
        )
    return refreshed_job


def fetch_analysis(client: TestClient, analysis_id: str) -> dict[str, Any]:
    response = client.get(f"/api/document-analyses/{analysis_id}")
    require_ok(response, f"analysis {analysis_id}")
    return response.json()


def fetch_job_result(client: TestClient, job_id: str) -> dict[str, Any]:
    response = client.get(f"/api/jobs/{job_id}/result")
    require_ok(response, f"job {job_id} result")
    return response.json()


def build_result(
    *,
    name: str,
    route: str,
    status: str,
    analysis_record: dict[str, Any],
    job: dict[str, Any] | None,
    event_count: int | None,
) -> ScenarioResult:
    analysis = analysis_record["analysis"]
    return ScenarioResult(
        name=name,
        route=route,
        status=status,
        analysis_id=analysis_record["analysis_id"],
        job_id=job["job_id"] if job else None,
        job_source_type=job["metadata"].get("source_type") if job else None,
        analysis_source_type=analysis_record["source_type"],
        artifact_id=analysis_record.get("artifact_id"),
        summary_title=analysis["summary_title"],
        review_confidence=float(analysis["review_confidence"]),
        source_confidence=float(analysis["source_confidence"]),
        finding_types=tuple(finding["finding_type"] for finding in analysis["findings"]),
        event_count=event_count,
    )


def compare_results(results: list[ScenarioResult]) -> dict[str, object]:
    baseline = results[0]
    baseline_findings = set(baseline.finding_types)
    deltas = []
    for result in results[1:]:
        finding_set = set(result.finding_types)
        deltas.append(
            {
                "name": result.name,
                "same_summary_title": result.summary_title == baseline.summary_title,
                "missing_baseline_findings": sorted(baseline_findings - finding_set),
                "extra_findings": sorted(finding_set - baseline_findings),
                "review_confidence_delta": round(
                    result.review_confidence - baseline.review_confidence,
                    2,
                ),
                "source_confidence_delta": round(
                    result.source_confidence - baseline.source_confidence,
                    2,
                ),
            }
        )
    return {
        "baseline": baseline.name,
        "all_have_analysis": all(result.analysis_id for result in results),
        "all_have_findings": all(result.finding_types for result in results),
        "deltas": deltas,
    }


def require_ok(response: Any, label: str) -> None:
    if response.status_code < 400:
        return
    raise RuntimeError(f"{label}: HTTP {response.status_code} {response.text}")


def run_harness(contract_path: Path) -> dict[str, object]:
    ensure_contract_fixture(contract_path)
    contract_text = contract_path.read_text(encoding="utf-8").strip()
    run_id = uuid4().hex[:8]
    user_id = f"user_scanner_harness_{run_id}"
    session_id = f"session_scanner_harness_{run_id}"

    with TemporaryDirectory(prefix="new-era-scanner-harness-") as temp_dir:
        storage_path = Path(temp_dir) / "runtime.sqlite3"
        app = create_app(storage_path=storage_path, enable_dev_auth=True)
        headers = {"X-New-Era-User-Id": user_id}
        with TestClient(app, headers=headers) as client:
            results = [
                run_direct_contract_text(
                    client,
                    user_id=user_id,
                    session_id=session_id,
                    contract_text=contract_text,
                ),
                run_upload_ocr(
                    client,
                    app,
                    user_id=user_id,
                    session_id=session_id,
                    contract_text=contract_text,
                ),
                run_scanner_text(
                    client,
                    app,
                    user_id=user_id,
                    session_id=session_id,
                    contract_text=contract_text,
                ),
            ]
    return {
        "contract_path": str(contract_path),
        "results": [result.to_dict() for result in results],
        "comparison": compare_results(results),
    }


def print_text_summary(summary: dict[str, object]) -> None:
    print(f"scanner_comparison_harness contract={summary['contract_path']}")
    for result in summary["results"]:
        finding_types = ", ".join(result["finding_types"]) or "none"
        job_source = result["job_source_type"] or "-"
        print(
            "- {name}: status={status} title={title!r} "
            "findings=[{findings}] review={review:.2f} source={source:.2f} "
            "job_source={job_source} analysis_source={analysis_source}".format(
                name=result["name"],
                status=result["status"],
                title=result["summary_title"],
                findings=finding_types,
                review=result["review_confidence"],
                source=result["source_confidence"],
                job_source=job_source,
                analysis_source=result["analysis_source_type"],
            )
        )

    print("comparison:")
    comparison = summary["comparison"]
    print(
        f"- all_have_analysis={comparison['all_have_analysis']} "
        f"all_have_findings={comparison['all_have_findings']}"
    )
    for delta in comparison["deltas"]:
        print(
            "- {name}: same_title={same_title} missing={missing} extra={extra} "
            "review_delta={review_delta:+.2f} source_delta={source_delta:+.2f}".format(
                name=delta["name"],
                same_title=delta["same_summary_title"],
                missing=delta["missing_baseline_findings"],
                extra=delta["extra_findings"],
                review_delta=delta["review_confidence_delta"],
                source_delta=delta["source_confidence_delta"],
            )
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare direct contract text, current multipart OCR upload, and a "
            "simulated mobile_text_scanner text job against the local backend."
        )
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT_PATH,
        help="Path to the sample contract text fixture.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full comparison payload as JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_harness(args.contract)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print_text_summary(summary)

    comparison = summary["comparison"]
    return 0 if comparison["all_have_analysis"] and comparison["all_have_findings"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
