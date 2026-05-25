from unittest import TestCase

from new_era.domain.documents import DeterministicContractAnalyzer


class DeterministicContractAnalyzerTest(TestCase):
    def test_extracts_findings_excerpts_and_confidence(self) -> None:
        analyzer = DeterministicContractAnalyzer()

        analysis = analyzer.analyze(
            document_text=(
                "Plano com fidelidade de 12 meses, renovacao automatica por igual periodo "
                "e multa de cancelamento antecipado."
            ),
            source_confidence=0.93,
        )

        self.assertTrue(analysis.has_findings)
        self.assertEqual(analysis.summary_title, "Contract clause needs attention")
        self.assertGreaterEqual(analysis.review_confidence, 0.6)
        self.assertEqual(len(analysis.findings), 3)
        self.assertIn("renovacao automatica", analysis.findings[0].excerpt.lower())

    def test_returns_low_confidence_when_no_risk_signal_is_found(self) -> None:
        analyzer = DeterministicContractAnalyzer()

        analysis = analyzer.analyze(
            document_text="Horario de atendimento de segunda a sexta.",
            source_confidence=0.92,
        )

        self.assertFalse(analysis.has_findings)
        self.assertLess(analysis.review_confidence, 0.45)
        self.assertIn("No known renewal", analysis.summary_body)
