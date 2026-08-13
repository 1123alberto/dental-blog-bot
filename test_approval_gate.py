import unittest
from datetime import date
from pathlib import Path

from approval_gate import (
    CLINICAL_REVIEW_PR,
    DIRECT_PUBLISH,
    NO_PUBLICATION,
    draft_pr_body,
    publication_plan,
    review_branch_name,
)
from agents.clinical_review import AUTOMATED_DRAFT, CLINICAL_REVIEW_REQUIRED


class TestApprovalGate(unittest.TestCase):
    def test_low_risk_is_direct_and_required_review_never_is(self):
        direct = publication_plan({"status": AUTOMATED_DRAFT, "article_id": "ordinary"})
        required = publication_plan({"status": CLINICAL_REVIEW_REQUIRED, "article_id": "implant-risk", "review_required_reasons": ["clinical_risk_topic"]}, date(2026, 8, 17))
        self.assertEqual(direct["publication_action"], DIRECT_PUBLISH)
        self.assertEqual(required["publication_action"], CLINICAL_REVIEW_PR)
        self.assertNotEqual(required["publication_action"], DIRECT_PUBLISH)

    def test_branch_is_deterministic_sanitized_and_namespaced(self):
        value = review_branch_name("Implant Failure / 100% Risk!", date(2026, 8, 17))
        self.assertEqual(value, "clinical-review/blog-2026-08-17-implant-failure-100-risk")
        self.assertEqual(value, review_branch_name("Implant Failure / 100% Risk!", date(2026, 8, 17)))

    def test_malformed_review_metadata_fails_closed(self):
        with self.assertRaises(ValueError):
            publication_plan({"status": CLINICAL_REVIEW_REQUIRED, "article_id": "", "review_required_reasons": []})
        with self.assertRaises(ValueError):
            publication_plan({"status": "clinically_reviewed", "article_id": "x"})

    def test_pr_body_is_compact_truthful_and_contains_review_reasons(self):
        brief = {
            "candidate_title": "Implant complication guidance",
            "source": {"name": "Journal", "published_date": "2026-08-17"},
            "evidence_maturity": "early research",
            "claims": [{"claim": "A supported 12% finding.", "evidence_excerpt": "raw source body must not appear"}],
            "recommended_internal_links": [{"target_path": "implants.html"}],
            "full_text": "SECRET RAW ARTICLE BODY",
        }
        plan = {"article_id": "implant", "review_reasons": ["early_research", "numeric_outcome_claim"]}
        body = draft_pr_body(brief, {"en": "Implant risks", "el": "Κίνδυνοι εμφυτευμάτων"}, plan)
        self.assertIn("early_research", body)
        self.assertIn("Merge this PR only after clinical review is complete.", body)
        self.assertIn("Numeric/statistical claims present: yes", body)
        self.assertNotIn("SECRET RAW ARTICLE BODY", body)
        self.assertNotIn("Clinically reviewed by", body)

    def test_workflow_has_draft_fail_closed_and_no_master_push_for_review_case(self):
        workflow = (Path(__file__).parent / ".github/workflows/weekly_blog.yml").read_text(encoding="utf-8")
        self.assertIn("clinical_review_pr)", workflow)
        self.assertIn("gh pr create --repo 1123alberto/dentplant-new --draft --base master", workflow)
        self.assertIn("git push -u origin \"$branch\"", workflow)
        self.assertIn("Review branch exists without an open PR; refusing to overwrite it.", workflow)
        self.assertIn("Reusing existing clinical-review PR", workflow)
        review_case = workflow.split("clinical_review_pr)", 1)[1].split("none)", 1)[0]
        self.assertNotIn("git push origin master", review_case)


if __name__ == "__main__":
    unittest.main()
