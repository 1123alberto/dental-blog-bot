"""Fail-closed internal-link planning, rendering, and publisher template tests."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.content_brief import build_content_brief
from internal_links import LinkPlanValidationError, parse_link_plan, render_internal_links
import publisher


def candidate():
    return {
        "title": "Dental implant maintenance and long-term outcomes",
        "source": "Journal of Clinical Dentistry",
        "link": "https://example.test/source",
        "date": "Aug 12, 2026",
        "summary": "The study discusses implant maintenance and follow-up care for long-term outcomes.",
        "related_dentplant_pages": ["implants.html", "article-timeline.html"],
        "strategic_scores": {"cannibalization_risk": 2},
    }


def markdown_with_plan(brief, mutate=None):
    links = brief["recommended_internal_links"]
    en = "Dentplant explains " + " and ".join(link["anchor_en"] for link in links) + "."
    el = "Το Dentplant εξηγεί " + " και ".join(link["anchor_el"] for link in links) + "."
    directives = []
    for index, link in enumerate(links, 1):
        target = mutate(link["target_path"], index) if mutate else link["target_path"]
        directives.extend([
            f"[LINK_{index}_TARGET]: {target}",
            f"[LINK_{index}_ANCHOR_EN]: {link['anchor_en']}",
            f"[LINK_{index}_ANCHOR_EL]: {link['anchor_el']}",
            f"[LINK_{index}_CONTEXT_EN]: {link['reason']}",
            f"[LINK_{index}_CONTEXT_EL]: {link['reason']}",
        ])
    directive_text = "\n".join(directives)
    return f"""[SOURCE]: Journal of Clinical Dentistry
[DATE]: Aug 12, 2026
[IMAGE_URL]:

--- ENGLISH VERSION ---
[EN_TITLE]: Implant Maintenance
[EN_TEASER]: Evidence-based maintenance guidance.
[EN_CONTENT]:
{en}

--- GREEK VERSION ---
[EL_TITLE]: Συντήρηση Εμφυτευμάτων
[EL_TEASER]: Ενημέρωση για συντήρηση.
[EL_CONTENT]:
{el}

--- INTERNAL LINK PLAN ---
{directive_text}"""


class TestInternalLinks(unittest.TestCase):
    def setUp(self):
        self.brief = build_content_brief(candidate())
        self.markdown = markdown_with_plan(self.brief)

    def test_valid_plan_renders_paired_links_once_per_language(self):
        plan = parse_link_plan(self.markdown)
        rendered, report = render_internal_links(self.markdown, self.brief)
        self.assertEqual(len(plan), len(self.brief["recommended_internal_links"]))
        self.assertTrue(report["valid"])
        self.assertEqual(len(report["links"]["en"]), len(plan))
        self.assertEqual(
            [link["href"] for link in report["links"]["en"]],
            [link["href"] for link in report["links"]["el"]],
        )
        for link in self.brief["recommended_internal_links"]:
            self.assertEqual(rendered.count(f"](../{link['target_path']})"), 2)

    def test_rejects_unapproved_external_traversal_and_malformed_targets(self):
        for target in ("other.html", "https://evil.example/x", "../implants.html", "implants.html?x=1"):
            with self.assertRaises(LinkPlanValidationError):
                render_internal_links(markdown_with_plan(self.brief, lambda _, index: target if index == 1 else _), self.brief)
        malformed = self.markdown.replace("[LINK_1_ANCHOR_EL]:", "[LINK_1_BAD]:")
        with self.assertRaises(LinkPlanValidationError):
            render_internal_links(malformed, self.brief)

    def test_rejects_duplicate_target(self):
        first = self.brief["recommended_internal_links"][0]["target_path"]
        duplicate = markdown_with_plan(self.brief, lambda _, index: first)
        with self.assertRaises(LinkPlanValidationError):
            render_internal_links(duplicate, self.brief)

    def test_missing_prose_anchor_degrades_gracefully_reporting_skipped_and_inserted(self):
        cand = {
            "title": "Dental implant maintenance and long-term outcomes",
            "source": "Journal of Clinical Dentistry",
            "link": "https://example.test/source",
            "date": "Aug 12, 2026",
            "summary": "The study discusses implant maintenance and follow-up care for long-term outcomes.",
            "related_dentplant_pages": ["implant-single-tooth.html", "porcelain-veneers.html"],
            "strategic_scores": {"cannibalization_risk": 2},
        }
        brief = build_content_brief(cand)
        markdown = markdown_with_plan(brief)

        # A. All anchors present
        rendered_all, report_all = render_internal_links(markdown, brief)
        self.assertTrue(report_all["valid"])
        self.assertEqual(len(report_all["inserted_links"]), 4)
        self.assertEqual(len(report_all["skipped_links"]), 0)

        # B. One EN anchor absent
        link0 = brief["recommended_internal_links"][0]
        markdown_no_en0 = markdown.replace(link0["anchor_en"], "omitted anchor text", 1)
        rendered_b, report_b = render_internal_links(markdown_no_en0, brief)
        self.assertTrue(report_b["valid"])
        self.assertEqual(len(report_b["inserted_links"]), 3)
        self.assertEqual(len(report_b["skipped_links"]), 1)
        self.assertEqual(report_b["skipped_links"][0], {
            "target_path": link0["target_path"],
            "language": "en",
            "anchor": link0["anchor_en"],
            "reason": "anchor_not_found",
        })

        # C. One EL anchor absent
        markdown_no_el0 = markdown.replace(link0["anchor_el"], "omitted Greek text", 1)
        rendered_c, report_c = render_internal_links(markdown_no_el0, brief)
        self.assertTrue(report_c["valid"])
        self.assertEqual(len(report_c["inserted_links"]), 3)
        self.assertEqual(len(report_c["skipped_links"]), 1)
        self.assertEqual(report_c["skipped_links"][0], {
            "target_path": link0["target_path"],
            "language": "el",
            "anchor": link0["anchor_el"],
            "reason": "anchor_not_found",
        })

        # D. Multiple anchors absent
        link1 = brief["recommended_internal_links"][1]
        markdown_multi = markdown.replace(link0["anchor_en"], "omitted EN", 1).replace(link1["anchor_el"], "omitted EL", 1)
        rendered_d, report_d = render_internal_links(markdown_multi, brief)
        self.assertTrue(report_d["valid"])
        self.assertEqual(len(report_d["inserted_links"]), 2)
        self.assertEqual(len(report_d["skipped_links"]), 2)
        skipped_keys = [(s["target_path"], s["language"]) for s in report_d["skipped_links"]]
        self.assertIn((link0["target_path"], "en"), skipped_keys)
        self.assertIn((link1["target_path"], "el"), skipped_keys)

    def test_strict_fail_closed_validations(self):
        from internal_links import _replace_anchor_once, validate_rendered_links

        # E. Altered directive anchor -> hard failure
        tampered_directive = self.markdown.replace(self.brief["recommended_internal_links"][0]["anchor_en"], "Altered Anchor Text")
        with self.assertRaises(LinkPlanValidationError):
            render_internal_links(tampered_directive, self.brief)

        # F. Unauthorized target -> hard failure
        unauthorized = self.markdown.replace(f"[LINK_1_TARGET]: {self.brief['recommended_internal_links'][0]['target_path']}", "[LINK_1_TARGET]: unapproved-page.html")
        with self.assertRaises(LinkPlanValidationError):
            render_internal_links(unauthorized, self.brief)

        # G. External URL / traversal / query / fragment -> hard failure
        for bad_target in ("https://evil.example/x", "../implants.html", "implants.html?x=1"):
            bad_md = self.markdown.replace(f"[LINK_1_TARGET]: {self.brief['recommended_internal_links'][0]['target_path']}", f"[LINK_1_TARGET]: {bad_target}")
            with self.assertRaises(LinkPlanValidationError):
                render_internal_links(bad_md, self.brief)

        # H. Corrupted rendered anchor text -> hard failure
        rendered_good, _ = render_internal_links(self.markdown, self.brief)
        corrupted_html = rendered_good.replace(self.brief["recommended_internal_links"][0]["anchor_en"], "Corrupted Text")
        with self.assertRaises(LinkPlanValidationError):
            validate_rendered_links(corrupted_html, self.brief["recommended_internal_links"])

        # I. Extra unauthorized rendered internal link -> hard failure
        extra_link_html = rendered_good.replace("[EN_CONTENT]:\n", "[EN_CONTENT]:\n[Extra Link](../unauthorized.html)\n")
        with self.assertRaises(LinkPlanValidationError):
            validate_rendered_links(extra_link_html, self.brief["recommended_internal_links"])

        # J. Direct _replace_anchor_once with missing anchor -> hard failure
        with self.assertRaises(LinkPlanValidationError):
            _replace_anchor_once("prose without anchor", "missing anchor", "../target.html")

    def test_publisher_fails_before_writing_on_link_validation_error(self):
        bad = markdown_with_plan(self.brief, lambda _, index: "https://evil.example" if index == 1 else _)
        with patch.object(publisher, "publish_bilingual_data") as publish:
            self.assertIsNone(publisher.publish_blog_post(bad, content_brief=self.brief))
        publish.assert_not_called()

    def test_publisher_template_uses_links_and_seo_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "article"
            website_data = Path(tmp) / "data" / "posts.json"
            website_data.parent.mkdir()
            with (
                patch.object(publisher, "OUTPUT_DIR", str(output_dir)),
                patch.object(publisher, "BASE_DIR", tmp),
                patch.object(publisher, "WEBSITE_DATA_PATH", str(website_data)),
                patch.object(publisher, "LOCAL_OUTPUT_DIR", str(Path(tmp) / "bot-output")),
                patch.object(publisher, "load_merged_posts", return_value=[]),
                patch.object(publisher, "update_static_blog_html", return_value=True),
                patch.object(publisher, "create_google_post_assets", return_value=None),
            ):
                path = publisher.publish_blog_post(self.markdown, content_brief=self.brief)
            html = Path(path).read_text(encoding="utf-8")
            self.assertIn('href="../implants.html"', html)
            self.assertNotIn("Dental News", html)
            self.assertNotIn("Breakthrough News", html)
            self.assertIn("Implantology", html)
            self.assertIn("Source publication date:", html)
            self.assertIn("Dentplant article published:", html)
            self.assertIn('<title>Συντήρηση Εμφυτευμάτων | Dentplant</title>', html)
            self.assertIn('"headline": "Συντήρηση Εμφυτευμάτων"', html)
            self.assertIn('"mainEntityOfPage"', html)
            self.assertIn('"datePublished"', html)
            self.assertIn('"author": {', html)
            self.assertIn('"name": "Dentplant"', html)
            self.assertNotIn("Dr. Angelo Moshopoulos", html)


if __name__ == "__main__":
    unittest.main()
