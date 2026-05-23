from unittest import TestCase

from new_era.domain.observations import Observation, ObservationKind
from new_era.infrastructure.observations import SimpleSimulationObservationAdapter


class SimpleSimulationObservationAdapterTest(TestCase):
    def test_creates_grocery_alert_candidate_from_missing_item_observation(self) -> None:
        adapter = SimpleSimulationObservationAdapter()
        observation = Observation(
            observation_id="obs_1",
            user_id="user_1",
            session_id="session_1",
            module="grocery",
            kind=ObservationKind.GROCERY_MISSING_ITEM,
            summary="Missing eggs in grocery session",
            metadata={"item_name": "eggs", "confidence": 0.88},
        )

        candidate = adapter.to_alert_candidate(observation)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.title, "Missing eggs")
        self.assertEqual(candidate.body, "You still need eggs.")
        self.assertEqual(candidate.metadata["observation_id"], "obs_1")

    def test_uses_safe_default_when_item_name_is_missing(self) -> None:
        adapter = SimpleSimulationObservationAdapter()
        observation = Observation(
            observation_id="obs_2",
            user_id="user_1",
            session_id="session_1",
            module="grocery",
            kind=ObservationKind.GROCERY_MISSING_ITEM,
            summary="Missing item",
            metadata={},
        )

        candidate = adapter.to_alert_candidate(observation)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.title, "Missing item")

    def test_creates_document_alert_candidate_from_contract_risk_observation(self) -> None:
        adapter = SimpleSimulationObservationAdapter()
        observation = Observation(
            observation_id="obs_3",
            user_id="user_1",
            session_id="session_1",
            module="documents",
            kind=ObservationKind.DOCUMENT_CONTRACT_REVIEW,
            summary="Contract review requested",
            metadata={
                "document_text": (
                    "Contrato com renovacao automatica, multa de cancelamento "
                    "e fidelidade de 12 meses."
                ),
                "confidence": 0.91,
            },
        )

        candidate = adapter.to_alert_candidate(observation)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.title, "Contract clause needs attention")
        self.assertEqual(candidate.category, "documents")
        self.assertIn("automatic renewal", candidate.body)

    def test_returns_none_for_document_observation_without_detected_risk(self) -> None:
        adapter = SimpleSimulationObservationAdapter()
        observation = Observation(
            observation_id="obs_4",
            user_id="user_1",
            session_id="session_1",
            module="documents",
            kind=ObservationKind.DOCUMENT_CONTRACT_REVIEW,
            summary="Contract review requested",
            metadata={
                "document_text": "Horario de atendimento de segunda a sexta.",
                "confidence": 0.91,
            },
        )

        candidate = adapter.to_alert_candidate(observation)

        self.assertIsNone(candidate)
