"""Tests that the weekly decision compares all supplied editorial finalists."""

import importlib.util
import unittest
from pathlib import Path


def load_decision_module():
    spec = importlib.util.spec_from_file_location(
        "content_decision_agent", Path(__file__).parent / "agents" / "content_decision_agent.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


decision_module = load_decision_module()


def candidate(title, editorial=44, strategic=None, related=None):
    return {
        "title": title,
        "source": "Journal of Clinical Dentistry",
        "scores": {"quality": editorial},
        "final_score": editorial,
        "strategic_scores": strategic or {
            "cluster_contribution": 8, "service_relevance": 8, "patient_intent_fit": 9,
            "content_gap_value": 10, "internal_link_opportunity": 8, "cannibalization_risk": 0,
        },
        "related_dentplant_pages": related or ["implants.html"],
        "is_promotional": False,
        "is_low_quality": False,
        "is_us_centric": False,
    }


MARGINAL_CREATE = {
    "cluster_contribution": 6, "service_relevance": 6, "patient_intent_fit": 6,
    "content_gap_value": 6, "internal_link_opportunity": 8, "cannibalization_risk": 4,
}
MARGINAL_UPDATE = {
    "cluster_contribution": 7, "service_relevance": 7, "patient_intent_fit": 7,
    "content_gap_value": 5, "internal_link_opportunity": 4, "cannibalization_risk": 5,
}
STRONG_UPDATE = {
    "cluster_contribution": 9, "service_relevance": 9, "patient_intent_fit": 9,
    "content_gap_value": 3, "internal_link_opportunity": 8, "cannibalization_risk": 8,
}
WEAK = {
    "cluster_contribution": 1, "service_relevance": 1, "patient_intent_fit": 1,
    "content_gap_value": 1, "internal_link_opportunity": 1, "cannibalization_risk": 1,
}


class TestMultiCandidateDecision(unittest.TestCase):
    def setUp(self):
        self.agent = decision_module.ContentDecisionAgent()

    def test_candidate_two_can_beat_editorial_candidate_one_for_create(self):
        result = self.agent.decide([
            candidate("Editorial #1", editorial=32, strategic=MARGINAL_CREATE),
            candidate("Distinct #2", editorial=44),
            candidate("Weak #3", editorial=10, strategic=WEAK),
        ])
        self.assertEqual(result["decision"], decision_module.DECISION_CREATE)
        self.assertEqual(result["candidate_title"], "Distinct #2")
        self.assertEqual(result["candidate_rank"], 2)
        self.assertEqual(result["evaluated_candidate_count"], 3)

    def test_candidate_three_can_win_when_first_two_fail(self):
        result = self.agent.decide([
            candidate("Weak #1", editorial=10, strategic=WEAK),
            candidate("Weak #2", editorial=12, strategic=WEAK),
            candidate("Strong #3", editorial=44),
        ])
        self.assertEqual(result["candidate_title"], "Strong #3")
        self.assertEqual(result["candidate_rank"], 3)

    def test_high_value_update_beats_weak_create(self):
        result = self.agent.decide([
            candidate("Weak distinct article", editorial=32, strategic=MARGINAL_CREATE),
            candidate("High-value update", editorial=44, strategic=STRONG_UPDATE),
        ])
        self.assertEqual(result["decision"], decision_module.DECISION_UPDATE)
        self.assertEqual(result["candidate_title"], "High-value update")
        self.assertEqual(result["recommended_target_page"], "implants.html")

    def test_strong_create_beats_marginal_update(self):
        result = self.agent.decide([
            candidate("Marginal update", editorial=30, strategic=MARGINAL_UPDATE),
            candidate("Strong distinct article", editorial=44),
        ])
        self.assertEqual(result["decision"], decision_module.DECISION_CREATE)
        self.assertEqual(result["candidate_title"], "Strong distinct article")

    def test_skip_only_when_every_candidate_fails(self):
        result = self.agent.decide([
            candidate("Weak #1", editorial=10, strategic=WEAK),
            candidate("Weak #2", editorial=11, strategic=WEAK),
            candidate("Weak #3", editorial=12, strategic=WEAK),
        ])
        self.assertEqual(result["decision"], decision_module.DECISION_SKIP)

    def test_same_candidate_set_is_deterministic(self):
        candidates = [candidate("One", editorial=32, strategic=MARGINAL_CREATE), candidate("Two", editorial=44)]
        self.assertEqual(self.agent.decide(candidates), self.agent.decide(candidates))


if __name__ == "__main__":
    unittest.main()
