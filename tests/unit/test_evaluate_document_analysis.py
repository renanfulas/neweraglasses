import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest import TestCase


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "tools" / "evaluate_document_analysis.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("evaluate_document_analysis", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class EvaluateDocumentAnalysisHarnessTest(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()
        cls.fixtures_dir = REPO_ROOT / "evals" / "document_analysis" / "fixtures"

    def test_discovers_and_runs_all_fixtures(self) -> None:
        paths = self.module.discover_fixture_paths(self.fixtures_dir)

        results = self.module.evaluate_fixtures(paths)
        summary = self.module.build_summary(results)

        self.assertEqual(len(paths), 3)
        self.assertTrue(summary["passed"])
        self.assertEqual(summary["passed_count"], 3)

    def test_plain_text_fixture_preserves_expected_findings(self) -> None:
        fixture = self.module.load_fixture(self.fixtures_dir / "plain_text_risk_signals.json")

        result = self.module.evaluate_fixture(fixture)

        self.assertTrue(result.passed)
        self.assertEqual(result.source_type, "plain_text")
        self.assertEqual(
            [finding["finding_type"] for finding in result.analysis["findings"]],
            ["automatic_renewal", "cancellation_fee", "minimum_commitment"],
        )

    def test_cli_json_output_reports_summary(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "--fixture",
                "evals/document_analysis/fixtures/plain_text_low_signal.json",
                "--json",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["results"][0]["fixture_id"], "plain_text_low_signal")
