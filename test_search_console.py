import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import search_console as sc
from agents.editorial_agent import add_strategic_evaluation
from agents.content_decision_agent import ContentDecisionAgent, DECISION_CREATE, DECISION_SKIP, DECISION_UPDATE


def row(query, page, impressions=100, clicks=5, ctr=.05, position=8):
    return {"keys": [query, page], "impressions": impressions, "clicks": clicks, "ctr": ctr, "position": position}


def candidate(**changes):
    base = {"title": "Dental implant maintenance guidance", "summary": "Implant maintenance guidance for patients.", "category": "Implantology",
            "scores": {"clinical_relevance": 8, "scientific_credibility": 8, "educational_value": 8, "innovation_significance": 6, "public_interest": 6, "practical_patient_relevance": 8},
            "is_promotional": False, "is_low_quality": False, "is_us_centric": False}
    base.update(changes); return base


class TestSearchConsole(unittest.TestCase):
    def test_windows_and_url_normalization_are_deterministic(self):
        recent, previous = sc.comparison_windows(date(2026, 8, 13))
        self.assertEqual(recent, {"start_date": "2026-07-16", "end_date": "2026-08-12"})
        self.assertEqual(previous, {"start_date": "2026-06-18", "end_date": "2026-07-15"})
        self.assertEqual(sc.normalize_dentplant_url("https://www.dentplant.gr/implants.html?a=1#x"), "implants.html")
        self.assertEqual(sc.normalize_dentplant_url("https://dentplant.gr/"), "index.html")
        self.assertIsNone(sc.normalize_dentplant_url("https://example.org/implants.html"))

    def test_response_parsing_snapshot_privacy_and_zero_safety(self):
        snapshot = sc.build_snapshot("https://www.dentplant.gr/", [row("implant maintenance", "https://www.dentplant.gr/implants.html"), row("bad", "https://elsewhere.test/x")], [], date(2026, 8, 13))
        self.assertEqual(snapshot["queries"][0]["page"], "implants.html")
        self.assertNotIn("bad", str(snapshot))
        self.assertEqual(sc.opportunity_scores({"impressions": 0}, {})["search_demand"], 0)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.json"; sc.save_snapshot({**snapshot, "credentials": "secret"}, path)
            self.assertNotIn("secret", path.read_text())

    def test_demand_ctr_ranking_and_trend_are_bounded(self):
        high = sc.opportunity_scores({"impressions": 400, "ctr": .02, "position": 8}, {"impressions": 100}, 10)
        tiny = sc.opportunity_scores({"impressions": 2, "ctr": 0, "position": 8}, {}, 10)
        first = sc.opportunity_scores({"impressions": 400, "ctr": .25, "position": 1}, {"impressions": 400}, 10)
        declining = sc.opportunity_scores({"impressions": 100, "ctr": .1, "position": 8}, {"impressions": 300}, 10)
        self.assertGreater(high["search_demand"], tiny["search_demand"])
        self.assertGreater(high["ctr_opportunity"], 0); self.assertGreater(high["ranking_opportunity"], first["ranking_opportunity"])
        self.assertGreater(high["trend"], 5); self.assertLess(declining["trend"], 5)

    def test_missing_credentials_is_graceful(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(sc.fetch_snapshot_from_api())

    def test_editorial_and_decision_integration(self):
        snapshot = sc.build_snapshot("https://www.dentplant.gr/", [row("implant maintenance", "https://www.dentplant.gr/implants.html", 400, 5, .01, 8)], [], date(2026, 8, 13))
        article = candidate(); add_strategic_evaluation([article], search_console_snapshot=snapshot)
        self.assertGreater(article["search_console_scores"]["search_demand"], 0)
        self.assertGreater(article["search_console_scores"]["existing_page_opportunity"], 0)
        # High overlap makes performance opportunity a strengthening recommendation, never an automatic rewrite.
        article["strategic_scores"].update({"cluster_contribution": 9, "service_relevance": 9, "patient_intent_fit": 9, "content_gap_value": 3, "cannibalization_risk": 7})
        self.assertEqual(ContentDecisionAgent().decide([article])["decision"], DECISION_UPDATE)
        # Strong distinct source keeps create possible with search demand.
        article["strategic_scores"].update({"content_gap_value": 8, "cannibalization_risk": 2})
        article["search_console_scores"]["existing_page_opportunity"] = 0
        self.assertEqual(ContentDecisionAgent().decide([article])["decision"], DECISION_CREATE)
        article["scores"] = {"clinical_relevance": 2}
        self.assertEqual(ContentDecisionAgent().decide([article])["decision"], DECISION_SKIP)


if __name__ == "__main__": unittest.main()
