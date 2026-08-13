"""Runtime tests for the weekly decision gate; all I/O beyond the decision record is mocked."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import main


def decision(kind, snapshot=None):
    return {
        "decision": kind,
        "candidate_title": "Evidence-based implant maintenance",
        "recommended_target_page": "implants.html" if kind == "UPDATE_EXISTING_PAGE" else None,
        "decision_score": 75.0,
        "reasons": ["Test decision."],
        "candidate_rank": 1,
        "evaluated_candidate_count": 1,
        "action_scores": {"create": 75.0, "update": None},
        "candidate_snapshot": snapshot or {
            "title": "Evidence-based implant maintenance",
            "strategic_scores": {"service_relevance": 8},
        },
    }


class TestRuntimeDecisionGate(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.decision_path = Path(self.temp_dir.name) / "weekly_decision.json"
        self.brief_path = Path(self.temp_dir.name) / "weekly_content_brief.json"
        self.review_path = Path(self.temp_dir.name) / "weekly_clinical_review.json"
        self.website_dir = Path(self.temp_dir.name) / "website"
        self.website_dir.mkdir()
        (self.website_dir / "sentinel.html").write_text("unchanged", encoding="utf-8")
        self.common = {
            "fetch_dental_news": MagicMock(return_value=[{"title": "Candidate"}]),
            "load_merged_posts": MagicMock(return_value=[]),
            "evaluate_article_candidates": MagicMock(return_value={
                "best_candidate": {"title": "Evidence-based implant maintenance"},
                "candidates": [{"title": "Evidence-based implant maintenance"}],
            }),
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_main(self, selected_decision, publish=None):
        publish = publish or MagicMock(return_value="/tmp/post.html")
        decision_agent = MagicMock()
        decision_agent.decide.return_value = selected_decision
        with (
            patch.object(main, "WEEKLY_DECISION_PATH", self.decision_path),
            patch.object(main, "WEEKLY_CONTENT_BRIEF_PATH", self.brief_path),
            patch.object(main, "WEEKLY_CLINICAL_REVIEW_PATH", self.review_path),
            patch.object(main, "fetch_dental_news", self.common["fetch_dental_news"]),
            patch.object(main, "load_merged_posts", self.common["load_merged_posts"]),
            patch.object(main, "evaluate_article_candidates", self.common["evaluate_article_candidates"]),
            patch.object(main, "ContentDecisionAgent", return_value=decision_agent),
            patch.object(main, "generate_blog_post_from_evaluation", return_value="draft") as generate,
            patch.object(main, "publish_blog_post", publish),
            patch("sys.argv", ["main.py"]),
        ):
            main.main()
        return generate, publish

    def test_create_reaches_article_generation_and_publisher(self):
        generate, publish = self.run_main(decision("CREATE_NEW_ARTICLE"))
        generate.assert_called_once()
        publish.assert_called_once()
        self.assertEqual(publish.call_args.args, ("draft",))
        self.assertIn("content_brief", publish.call_args.kwargs)
        record = json.loads(self.decision_path.read_text(encoding="utf-8"))
        self.assertEqual(record["runtime_action"], "article_generation_started")
        self.assertEqual(record["publication_action"], "direct_publish")
        self.assertTrue(self.review_path.exists())

    def test_review_required_create_emits_pr_handoff_not_direct_publish(self):
        with patch.object(main, "classify_clinical_review", return_value={
            "article_id": "implant-risk", "status": "clinical_review_required",
            "review_required_reasons": ["clinical_risk_topic"], "reviewer": None,
            "reviewed_at": None, "source": "automated_pipeline",
        }):
            self.run_main(decision("CREATE_NEW_ARTICLE"))
        record = json.loads(self.decision_path.read_text(encoding="utf-8"))
        self.assertEqual(record["publication_action"], "clinical_review_pr")
        self.assertTrue(record["review_branch"].startswith("clinical-review/blog-"))
        self.assertIn("clinical_risk_topic", record["draft_pr_body"])

    def test_update_does_not_generate_or_publish_and_exits_successfully(self):
        generate, publish = self.run_main(decision("UPDATE_EXISTING_PAGE"))
        generate.assert_not_called()
        publish.assert_not_called()
        self.assertEqual((self.website_dir / "sentinel.html").read_text(encoding="utf-8"), "unchanged")
        record = json.loads(self.decision_path.read_text(encoding="utf-8"))
        self.assertEqual(record["runtime_action"], "existing_page_update_recommended")
        self.assertEqual(record["recommended_target_page"], "implants.html")
        self.assertFalse(self.review_path.exists())

    def test_skip_does_not_generate_or_publish_and_exits_successfully(self):
        generate, publish = self.run_main(decision("SKIP_THIS_WEEK"))
        generate.assert_not_called()
        publish.assert_not_called()
        self.assertEqual((self.website_dir / "sentinel.html").read_text(encoding="utf-8"), "unchanged")
        record = json.loads(self.decision_path.read_text(encoding="utf-8"))
        self.assertEqual(record["runtime_action"], "publication_skipped")
        self.assertFalse(self.review_path.exists())

    def test_malformed_or_unknown_decision_fails_explicitly(self):
        with self.assertRaises(RuntimeError):
            self.run_main({"decision": "NOT_A_DECISION", "reasons": []})

    def test_decision_record_removes_raw_article_body(self):
        snapshot = {
            "title": "Safe title",
            "source": "Journal",
            "full_text": "This entire source article must not be persisted.",
            "summary": "Nor should raw summaries.",
            "strategic_scores": {"service_relevance": 8},
        }
        self.run_main(decision("SKIP_THIS_WEEK", snapshot=snapshot))
        record = json.loads(self.decision_path.read_text(encoding="utf-8"))
        self.assertNotIn("full_text", record["candidate_snapshot"])
        self.assertNotIn("summary", record["candidate_snapshot"])

    def test_chosen_ranked_candidate_is_passed_to_generation_once(self):
        chosen = {"title": "Candidate #2"}
        evaluation = {"best_candidate": {"title": "Candidate #1"}, "candidates": [
            {"title": "Candidate #1"}, chosen, {"title": "Candidate #3"},
        ]}
        selected = decision("CREATE_NEW_ARTICLE")
        selected.update({"candidate_title": "Candidate #2", "candidate_rank": 2, "evaluated_candidate_count": 3})
        decision_agent = MagicMock()
        decision_agent.decide.return_value = selected
        with (
            patch.object(main, "WEEKLY_DECISION_PATH", self.decision_path),
            patch.object(main, "WEEKLY_CONTENT_BRIEF_PATH", self.brief_path),
            patch.object(main, "fetch_dental_news", return_value=[{"title": "News"}]),
            patch.object(main, "load_merged_posts", return_value=[]),
            patch.object(main, "evaluate_article_candidates", return_value=evaluation) as evaluate,
            patch.object(main, "ContentDecisionAgent", return_value=decision_agent),
            patch.object(main, "generate_blog_post_from_evaluation", return_value="draft") as generate,
            patch.object(main, "publish_blog_post", return_value="/tmp/post.html"),
            patch("sys.argv", ["main.py"]),
        ):
            main.main()
        evaluate.assert_called_once_with([{"title": "News"}], recent_posts=[], for_weekly_decision=True)
        self.assertIs(generate.call_args.args[0]["best_candidate"], chosen)


if __name__ == "__main__":
    unittest.main()
