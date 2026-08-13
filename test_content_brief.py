"""Focused tests for deterministic ContentBrief planning and safe persistence."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agents.content_brief import build_content_brief, load_content_map
import main


def candidate(**overrides):
    data = {
        "title": "Dental implant maintenance and long-term outcomes",
        "source": "Journal of Clinical Dentistry",
        "link": "https://example.test/implant-maintenance",
        "date": "Aug 12, 2026",
        "summary": "The study discusses implant maintenance and follow-up care for long-term outcomes.",
        "full_text": "The study discusses implant maintenance and follow-up care for long-term outcomes. It does not provide a universal outcome percentage.",
        "clinical_risk_topic": False,
        "strategic_scores": {"cannibalization_risk": 3},
        "related_dentplant_pages": ["implants.html", "implant-single-tooth.html", "article-timeline.html"],
    }
    data.update(overrides)
    return data


class TestContentBrief(unittest.TestCase):
    def test_source_provenance_and_missing_metadata(self):
        brief = build_content_brief(candidate())
        self.assertEqual(brief["source"]["name"], "Journal of Clinical Dentistry")
        self.assertEqual(brief["source"]["url"], "https://example.test/implant-maintenance")
        missing = build_content_brief(candidate(source=None, link=None, date=None))
        self.assertIsNone(missing["source"]["name"])
        self.assertIsNone(missing["source"]["url"])
        self.assertIsNone(missing["source"]["published_date"])

    def test_claims_remain_within_supplied_text_without_statistics(self):
        brief = build_content_brief(candidate())
        supplied = candidate()["summary"]
        for claim in brief["claims"]:
            self.assertIn(claim["claim"], supplied)
            self.assertNotIn("%", claim["claim"])

    def test_evidence_maturity_and_valid_cluster_pages_and_links(self):
        brief = build_content_brief(candidate(summary="A pilot study of implant maintenance was reported."))
        self.assertEqual(brief["evidence_maturity"], "early research")
        paths = {page["path"] for page in load_content_map()["pages"]}
        self.assertEqual(brief["primary_cluster"], "implants")
        self.assertIn("implants.html", brief["related_dentplant_pages"])
        self.assertTrue(brief["recommended_internal_links"])
        anchors = set()
        for link in brief["recommended_internal_links"]:
            self.assertIn(link["target_path"], paths)
            self.assertTrue(link["anchor_en"].strip())
            self.assertNotIn("click here", link["anchor_en"].lower())
            self.assertNotIn(link["anchor_en"].lower(), anchors)
            anchors.add(link["anchor_en"].lower())

    def test_duplication_and_balanced_risk_guidance(self):
        risk_brief = build_content_brief(candidate(
            title="Dental implant complications and maintenance",
            summary="The source discusses complication warning signs and follow-up care.",
            clinical_risk_topic=True,
            strategic_scores={"cannibalization_risk": 7},
        ))
        self.assertTrue(risk_brief["clinical_risk_notes"])
        self.assertTrue(risk_brief["duplication_avoidance"])
        ordinary = build_content_brief(candidate())
        self.assertEqual(ordinary["clinical_risk_notes"], [])

    def test_brief_does_not_include_full_source_body_and_is_deterministic(self):
        article = candidate(full_text="SECRET LONG SOURCE BODY " * 100)
        first = build_content_brief(article, recent_titles=["Previous article"])
        second = build_content_brief(article, recent_titles=["Previous article"])
        self.assertEqual(first, second)
        serialized = json.dumps(first)
        self.assertNotIn("SECRET LONG SOURCE BODY", serialized)
        self.assertNotIn("full_text", serialized)

    def test_update_and_skip_do_not_create_content_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            brief_path = Path(tmp) / "weekly_content_brief.json"
            for kind in ("UPDATE_EXISTING_PAGE", "SKIP_THIS_WEEK"):
                decision = {
                    "decision": kind, "candidate_title": "Candidate", "decision_score": 1,
                    "reasons": ["Test"], "candidate_snapshot": {}, "candidate_rank": 1,
                    "evaluated_candidate_count": 1, "action_scores": {},
                    "recommended_target_page": "implants.html" if kind == "UPDATE_EXISTING_PAGE" else None,
                }
                agent = MagicMock(); agent.decide.return_value = decision
                with (
                    patch.object(main, "WEEKLY_DECISION_PATH", Path(tmp) / "decision.json"),
                    patch.object(main, "WEEKLY_CONTENT_BRIEF_PATH", brief_path),
                    patch.object(main, "fetch_dental_news", return_value=[{"title": "Candidate"}]),
                    patch.object(main, "load_merged_posts", return_value=[]),
                    patch.object(main, "evaluate_article_candidates", return_value={"best_candidate": {"title": "Candidate"}, "candidates": [{"title": "Candidate"}]}),
                    patch.object(main, "ContentDecisionAgent", return_value=agent),
                    patch.object(main, "generate_blog_post_from_evaluation") as generate,
                    patch.object(main, "publish_blog_post") as publish,
                    patch("sys.argv", ["main.py"]),
                ):
                    main.main()
                generate.assert_not_called(); publish.assert_not_called()
                self.assertFalse(brief_path.exists())

    def test_create_persists_compact_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            brief_path = Path(tmp) / "weekly_content_brief.json"
            chosen = candidate(full_text="UNPERSISTED BODY " * 50)
            decision = {
                "decision": "CREATE_NEW_ARTICLE", "candidate_title": chosen["title"], "decision_score": 50,
                "reasons": ["Test"], "candidate_snapshot": {}, "candidate_rank": 1,
                "evaluated_candidate_count": 1, "action_scores": {}, "recommended_target_page": None,
            }
            agent = MagicMock(); agent.decide.return_value = decision
            with (
                patch.object(main, "WEEKLY_DECISION_PATH", Path(tmp) / "decision.json"),
                patch.object(main, "WEEKLY_CONTENT_BRIEF_PATH", brief_path),
                patch.object(main, "fetch_dental_news", return_value=[{"title": "Candidate"}]),
                patch.object(main, "load_merged_posts", return_value=[]),
                patch.object(main, "evaluate_article_candidates", return_value={"best_candidate": chosen, "candidates": [chosen]}),
                patch.object(main, "ContentDecisionAgent", return_value=agent),
                patch.object(main, "generate_blog_post_from_evaluation", return_value="draft") as generate,
                patch.object(main, "publish_blog_post", return_value="/tmp/post.html"),
                patch("sys.argv", ["main.py"]),
            ):
                main.main()
            persisted = brief_path.read_text(encoding="utf-8")
            self.assertNotIn("UNPERSISTED BODY", persisted)
            self.assertNotIn("full_text", persisted)
            passed_brief = generate.call_args.args[0]["content_brief"]
            self.assertEqual(passed_brief["candidate_title"], chosen["title"])
            self.assertEqual(passed_brief["recommended_internal_links"], build_content_brief(chosen)["recommended_internal_links"])


if __name__ == "__main__":
    unittest.main()
