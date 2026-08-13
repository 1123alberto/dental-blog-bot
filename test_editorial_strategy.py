"""Focused, dependency-light tests for Dentplant-aware editorial scoring."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path


def load_editorial_module():
    """Load the scorer directly so these tests do not require API client packages."""
    package = types.ModuleType("agents")
    package.__path__ = []
    base = types.ModuleType("agents.base")

    class BaseAgent:
        def __init__(self, client=None, model_name=None):
            self.client = client
            self.model_name = model_name

    base.BaseAgent = BaseAgent
    sys.modules["agents"] = package
    sys.modules["agents.base"] = base
    module_path = Path(__file__).parent / "agents" / "editorial_agent.py"
    spec = importlib.util.spec_from_file_location("agents.editorial_agent", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


editorial = load_editorial_module()


class TestDentplantEditorialStrategy(unittest.TestCase):
    def test_content_map_loads(self):
        content_map = editorial.load_content_map()
        self.assertGreater(len(content_map["pages"]), 0)

    def test_treatment_topic_has_service_and_cluster_value(self):
        scores, related, _, _ = editorial.evaluate_dentplant_strategy({
            "title": "Dental implant treatment recovery and long-term outcomes",
            "summary": "Patient guidance for implant treatment.",
        })
        self.assertGreaterEqual(scores["service_relevance"], 8)
        self.assertGreaterEqual(scores["cluster_contribution"], 8)
        self.assertIn("implants.html", related)

    def test_near_duplicate_intent_raises_cannibalization_risk(self):
        scores, related, _, _ = editorial.evaluate_dentplant_strategy({
            "title": "What do clear aligners cost and are they right for me?",
            "summary": "A clear aligner cost guide.",
        })
        self.assertGreaterEqual(scores["cannibalization_risk"], 4)
        self.assertIn("article-aligners-cost.html", related)

    def test_internal_link_opportunities_are_relevant(self):
        scores, related, _, _ = editorial.evaluate_dentplant_strategy({
            "title": "Dental implant recovery, risks, and treatment alternatives",
            "summary": "Patient decision support.",
        })
        self.assertGreaterEqual(scores["internal_link_opportunity"], 4)
        self.assertTrue(any(path.startswith("implant") for path in related))

    def test_unrelated_topic_has_lower_strategic_value(self):
        scores, related, _, _ = editorial.evaluate_dentplant_strategy({
            "title": "Celebrity magic toothpaste shocks social media",
            "summary": "Entertainment coverage.",
        })
        self.assertLess(scores["service_relevance"], 5)
        self.assertLess(scores["cluster_contribution"], 5)
        self.assertEqual(related, [])

    def test_clinical_risk_topic_is_not_automatically_rejected(self):
        article = editorial.heuristic_score_and_classify([{
            "title": "Implant failure risks and evidence-based treatment options",
            "source": "Journal of Clinical Dentistry",
            "summary": "Balanced patient education about risks and follow-up.",
        }])[0]
        self.assertTrue(article["clinical_risk_topic"])
        self.assertFalse(article["is_inappropriate"])
        self.assertFalse(article["is_low_quality"])

    def test_sensational_risk_content_remains_subject_to_quality_controls(self):
        article = editorial.heuristic_score_and_classify([{
            "title": "Shocking implant failure claims reveal insane secret",
            "source": "Celebrity Dental News",
            "summary": "Unsupported and alarming claims.",
        }])[0]
        self.assertTrue(article["clinical_risk_topic"])
        self.assertTrue(article["is_low_quality"])
        self.assertFalse(article["is_inappropriate"])

    def test_heuristic_fallback_populates_all_strategic_fields(self):
        article = editorial.heuristic_score_and_classify([{
            "title": "Dental implant maintenance guidance",
            "source": "Journal of Clinical Dentistry",
            "summary": "Long-term patient care.",
        }])[0]
        self.assertEqual(set(article["strategic_scores"]), set(editorial.STRATEGIC_SCORE_FIELDS))
        self.assertIn("related_dentplant_pages", article)
        self.assertIn("strategic_reasoning", article)

    def test_deduplication_and_history_filter_still_work(self):
        articles = editorial.deduplicate_articles([
            {"title": "Dental implants recovery study", "source": "Journal"},
            {"title": "Dental implants recovery report", "source": "Dental Tribune"},
        ])
        self.assertEqual(len(articles), 1)
        filtered = editorial.apply_history_filter(
            [{"title": "Dental implants recovery study"}], ["Dental implants recovery report"]
        )
        self.assertEqual(filtered[0]["history_penalty"], 40)

    def test_strategic_value_materially_affects_final_score(self):
        articles = editorial.heuristic_score_and_classify([
            {"title": "Dental implant treatment recovery", "source": "Journal", "summary": "Patient guidance."},
            {"title": "Celebrity magic toothpaste", "source": "Journal", "summary": "Entertainment."},
        ])
        ranked = editorial.get_top_3_candidates(articles)
        self.assertEqual(ranked[0]["title"], "Dental implant treatment recovery")
        self.assertGreater(ranked[0]["strategic_score"], ranked[1]["strategic_score"])


if __name__ == "__main__":
    unittest.main()
