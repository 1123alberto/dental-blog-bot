"""Focused tests for the deterministic weekly content decision layer."""

import importlib.util
import unittest
from pathlib import Path


def load_module():
    module_path = Path(__file__).parent / "agents" / "content_decision_agent.py"
    spec = importlib.util.spec_from_file_location("content_decision_agent", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


decision_module = load_module()


def candidate(title="Implant maintenance guide", **overrides):
    data = {
        "title": title,
        "source": "Journal of Clinical Dentistry",
        "category": "Implantology",
        "scores": {
            "clinical_relevance": 8,
            "scientific_credibility": 8,
            "educational_value": 8,
            "innovation_significance": 6,
            "public_interest": 6,
            "practical_patient_relevance": 8,
        },
        "final_score": 80,
        "strategic_scores": {
            "cluster_contribution": 8,
            "service_relevance": 8,
            "patient_intent_fit": 8,
            "content_gap_value": 8,
            "internal_link_opportunity": 6,
            "cannibalization_risk": 2,
        },
        "related_dentplant_pages": ["implants.html", "implant-single-tooth.html"],
        "is_promotional": False,
        "is_low_quality": False,
        "is_us_centric": False,
        "clinical_risk_topic": False,
    }
    data.update(overrides)
    return data


class TestContentDecisionAgent(unittest.TestCase):
    def setUp(self):
        self.agent = decision_module.ContentDecisionAgent()

    def test_strong_distinct_candidate_creates_article(self):
        result = self.agent.decide([candidate()])
        self.assertEqual(result["decision"], decision_module.DECISION_CREATE)
        self.assertIsNone(result["recommended_target_page"])

    def test_high_cannibalization_favors_update(self):
        result = self.agent.decide([candidate(
            title="Dental implant treatment and maintenance",
            strategic_scores={
                "cluster_contribution": 9, "service_relevance": 9, "patient_intent_fit": 9,
                "content_gap_value": 3, "internal_link_opportunity": 8, "cannibalization_risk": 8,
            },
        )])
        self.assertEqual(result["decision"], decision_module.DECISION_UPDATE)
        self.assertEqual(result["recommended_target_page"], "implants.html")

    def test_weak_irrelevant_candidate_skips(self):
        result = self.agent.decide([candidate(
            title="Celebrity dental gossip",
            scores={"clinical_relevance": 3},
            strategic_scores={field: 1 for field in decision_module._strategic_scores({})},
            related_dentplant_pages=[],
        )])
        self.assertEqual(result["decision"], decision_module.DECISION_SKIP)

    def test_low_editorial_quality_cannot_create(self):
        result = self.agent.decide([candidate(scores={"clinical_relevance": 9, "scientific_credibility": 9})])
        self.assertEqual(result["decision"], decision_module.DECISION_SKIP)

    def test_high_strategy_does_not_override_unacceptable_cannibalization(self):
        result = self.agent.decide([candidate(strategic_scores={
            "cluster_contribution": 10, "service_relevance": 10, "patient_intent_fit": 10,
            "content_gap_value": 8, "internal_link_opportunity": 10, "cannibalization_risk": 9,
        })])
        self.assertNotEqual(result["decision"], decision_module.DECISION_CREATE)

    def test_update_target_always_exists_in_map(self):
        result = self.agent.decide([candidate(strategic_scores={
            "cluster_contribution": 8, "service_relevance": 8, "patient_intent_fit": 8,
            "content_gap_value": 4, "internal_link_opportunity": 6, "cannibalization_risk": 6,
        })])
        paths = {page["path"] for page in self.agent.content_map["pages"]}
        self.assertEqual(result["decision"], decision_module.DECISION_UPDATE)
        self.assertIn(result["recommended_target_page"], paths)

    def test_nonexistent_target_is_never_returned(self):
        result = self.agent.decide([candidate(
            related_dentplant_pages=["does-not-exist.html"],
            strategic_scores={
                "cluster_contribution": 8, "service_relevance": 8, "patient_intent_fit": 8,
                "content_gap_value": 4, "internal_link_opportunity": 6, "cannibalization_risk": 6,
            },
        )])
        self.assertNotEqual(result["decision"], decision_module.DECISION_UPDATE)
        self.assertIsNone(result["recommended_target_page"])

    def test_clinical_risk_topic_can_create(self):
        result = self.agent.decide([candidate(
            title="Understanding implant complication risks and follow-up care",
            clinical_risk_topic=True,
        )])
        self.assertEqual(result["decision"], decision_module.DECISION_CREATE)

    def test_clinical_risk_topic_can_update(self):
        result = self.agent.decide([candidate(
            title="Dental implant complications and maintenance",
            clinical_risk_topic=True,
            strategic_scores={
                "cluster_contribution": 9, "service_relevance": 9, "patient_intent_fit": 9,
                "content_gap_value": 3, "internal_link_opportunity": 8, "cannibalization_risk": 8,
            },
        )])
        self.assertEqual(result["decision"], decision_module.DECISION_UPDATE)

    def test_no_candidates_skips(self):
        result = self.agent.decide([])
        self.assertEqual(result["decision"], decision_module.DECISION_SKIP)
        self.assertIsNone(result["candidate_title"])

    def test_identical_input_is_deterministic(self):
        candidates = [candidate()]
        self.assertEqual(self.agent.decide(candidates), self.agent.decide(candidates))


if __name__ == "__main__":
    unittest.main()
