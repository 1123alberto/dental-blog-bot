"""Tests for ContentBrief-aware copywriter prompts, directives, and QA checks."""

import unittest

from agents.content_brief import build_content_brief
from agents.copywriter_agent import CopywriterAgent
from agents.qa_agent import QAAgent


def candidate(**overrides):
    data = {
        "title": "Dental implant maintenance and long-term outcomes",
        "source": "Journal of Clinical Dentistry",
        "link": "https://example.test/implant-maintenance",
        "date": "Aug 12, 2026",
        "summary": "The study discusses implant maintenance and follow-up care for long-term outcomes.",
        "full_text": "The study discusses implant maintenance and follow-up care for long-term outcomes.",
        "related_dentplant_pages": ["implants.html", "article-timeline.html"],
        "strategic_scores": {"cannibalization_risk": 3},
        "clinical_risk_topic": False,
    }
    data.update(overrides)
    return data


class TestContentBriefCopywriter(unittest.TestCase):
    def setUp(self):
        self.candidate = candidate()
        self.brief = build_content_brief(self.candidate)

    def test_brief_reaches_bilingual_prompts_and_directives(self):
        prompts = []
        agent = CopywriterAgent(client=object())

        def fake_run_llm(prompt, **kwargs):
            prompts.append(prompt)
            if len(prompts) == 1:
                return "TITLE: Implant Maintenance\nTEASER: Helpful guidance.\nCONTENT:\nDentplant provides evidence-based care. Maintenance supports long-term outcomes."
            return "TITLE: Συντήρηση Εμφυτευμάτων\nTEASER: Χρήσιμη ενημέρωση.\nCONTENT:\nΤο Dentplant παρέχει φροντίδα βασισμένη σε τεκμήρια. Η συντήρηση υποστηρίζει μακροπρόθεσμα αποτελέσματα."

        agent.run_llm = fake_run_llm
        output = agent.write_post(self.candidate, content_brief=self.brief)
        combined_prompts = "\n".join(prompts)
        self.assertIn(self.brief["article_angle"], combined_prompts)
        self.assertIn(self.brief["primary_patient_intent"], combined_prompts)
        self.assertIn(self.brief["evidence_maturity"], combined_prompts)
        self.assertIn(self.brief["claims"][0]["claim"], combined_prompts)
        self.assertIn(self.brief["duplication_avoidance"][0], combined_prompts)
        self.assertIn(self.brief["editorial_constraints"][0], combined_prompts)
        self.assertIn("--- INTERNAL LINK PLAN ---", output)
        for link in self.brief["recommended_internal_links"]:
            self.assertIn(link["target_path"], output)
            self.assertIn(link["anchor_en"], output)
            self.assertIn(link["anchor_el"], output)

    def test_qa_rejects_unplanned_target_and_unsupported_statistic(self):
        qa = QAAgent()
        links = self.brief["recommended_internal_links"]
        valid_plan = "\n".join(
            f"[LINK_{i}_TARGET]: {link['target_path']}\n[LINK_{i}_ANCHOR_EN]: {link['anchor_en']}\n[LINK_{i}_ANCHOR_EL]: {link['anchor_el']}"
            for i, link in enumerate(links, 1)
        )
        markdown = f"""[SOURCE]: Journal
[DATE]: Aug 12, 2026
[IMAGE_URL]:
--- ENGLISH VERSION ---
[EN_TITLE]: Implant Maintenance
[EN_TEASER]: Guidance
[EN_CONTENT]:
Dentplant explains maintenance and long-term outcomes. 99% of patients benefit.
--- GREEK VERSION ---
[EL_TITLE]: Συντήρηση Εμφυτευμάτων
[EL_TEASER]: Ενημέρωση
[EL_CONTENT]:
Το Dentplant εξηγεί τη συντήρηση και τα μακροπρόθεσμα αποτελέσματα.
--- INTERNAL LINK PLAN ---
{valid_plan}
[LINK_99_TARGET]: unplanned-page.html
[LINK_99_ANCHOR_EN]: unplanned link
[LINK_99_ANCHOR_EL]: μη προγραμματισμένος σύνδεσμος
"""
        errors = qa._validate_content_brief_compliance(markdown, "maintenance 99%", "συντήρηση", self.brief)
        self.assertTrue(any("Unsupported statistic" in error for error in errors))
        self.assertTrue(any("targets do not match" in error for error in errors))

    def test_risk_notes_reach_prompt_without_affecting_ordinary_prompt(self):
        risk_brief = build_content_brief(candidate(
            title="Dental implant complication risks and maintenance",
            summary="The study discusses complication warning signs and maintenance.",
            clinical_risk_topic=True,
        ))
        agent = CopywriterAgent(client=object())
        risk_prompt = agent._brief_prompt_block(risk_brief)
        ordinary_prompt = agent._brief_prompt_block(self.brief)
        self.assertIn(risk_brief["clinical_risk_notes"][0], risk_prompt)
        self.assertIn("Clinical-risk notes:\n- None", ordinary_prompt)

    def test_refinement_replaces_substituted_link_plan_with_exact_brief_values(self):
        agent = CopywriterAgent(client=object())
        substituted = """[SOURCE]: Journal
[DATE]: Aug 12, 2026
[IMAGE_URL]:
--- ENGLISH VERSION ---
[EN_TITLE]: Implant Maintenance
[EN_TEASER]: Guidance
[EN_CONTENT]: Content
--- GREEK VERSION ---
[EL_TITLE]: Συντήρηση Εμφυτευμάτων
[EL_TEASER]: Ενημέρωση
[EL_CONTENT]: Περιεχόμενο
--- INTERNAL LINK PLAN ---
[LINK_1_TARGET]: wrong-page.html
[LINK_1_ANCHOR_EN]: substituted anchor
[LINK_1_ANCHOR_EL]: αντικατασταθείσα άγκυρα"""
        agent.run_llm = lambda *args, **kwargs: substituted

        refined = agent.refine_post("old draft", ["Fix wording"], self.candidate, content_brief=self.brief)

        self.assertNotIn("wrong-page.html", refined)
        self.assertNotIn("substituted anchor", refined)
        for index, link in enumerate(self.brief["recommended_internal_links"], 1):
            self.assertIn(f"[LINK_{index}_TARGET]: {link['target_path']}", refined)
            self.assertIn(f"[LINK_{index}_ANCHOR_EN]: {link['anchor_en']}", refined)
            self.assertIn(f"[LINK_{index}_ANCHOR_EL]: {link['anchor_el']}", refined)

    def test_five_links_boundary_space_anchors_roundtrip_qa(self):
        from internal_links import LinkPlanValidationError, parse_link_plan, validate_link_plan

        cand = candidate(
            title="Discussing alcohol use with patients",
            summary="Dentists discuss alcohol consumption with patients regarding oral health risks and periodontal outcomes.",
            full_text="Dentists discuss alcohol consumption with patients regarding oral health risks and periodontal outcomes.",
            related_dentplant_pages=[
                "treatment-periodontology.html",
                "article/news-2026-06-03.html",
                "article/news-2026-06-08.html",
                "article/news-2026-06-29.html",
                "article/news-2026-06-08-1.html",
            ],
        )
        brief = build_content_brief(cand)
        links = brief["recommended_internal_links"]
        self.assertEqual(len(links), 5)

        # 1. Link 3 and Link 4 anchors produced by ContentBrief no longer end in whitespace.
        for index in (2, 3):
            self.assertFalse(links[index]["anchor_en"].endswith(" "))
            self.assertFalse(links[index]["anchor_el"].endswith(" "))

        copywriter = CopywriterAgent(client=object())
        plan_text = copywriter._link_plan(brief)

        markdown = f"""[SOURCE]: Journal of Clinical Dentistry
[DATE]: Aug 12, 2026
[IMAGE_URL]:

--- ENGLISH VERSION ---
[EN_TITLE]: Discussing alcohol use with patients
[EN_TEASER]: Guidance
[EN_CONTENT]:
Dentists discuss alcohol consumption with patients regarding oral health risks. Dentplant provides evidence-based care.

--- GREEK VERSION ---
[EL_TITLE]: Συζήτηση για τη χρήση αλκοόλ με τους ασθενείς
[EL_TEASER]: Ενημέρωση
[EL_CONTENT]:
Οι οδοντίατροι συζητούν την κατανάλωση αλκοόλ με τους ασθενείς. Το Dentplant παρέχει φροντίδα.

{plan_text}"""

        # 2, 3, 4, 5. Targets, EN anchors, EL anchors round-trip & parse_link_plan preserves exact values
        parsed = parse_link_plan(markdown)
        self.assertEqual(len(parsed), 5)
        for expected, actual in zip(links, parsed):
            self.assertEqual(expected["target_path"], actual["target_path"])
            self.assertEqual(expected["anchor_en"], actual["anchor_en"])
            self.assertEqual(expected["anchor_el"], actual["anchor_el"])

        # 6. validate_link_plan() accepts them
        validated = validate_link_plan(parsed, brief)
        self.assertEqual(len(validated), 5)

        # 7. QAAgent.validate_post() no longer reports anchor mismatch for links 3 and 4
        qa = QAAgent()
        compliance_errors = qa._validate_content_brief_compliance(markdown, "Dentplant", "Dentplant", brief)
        anchor_errors = [e for e in compliance_errors if "Internal-link anchors" in e or "Internal-link target" in e]
        self.assertEqual(anchor_errors, [])

        # 8. Deliberately altering one anchor still causes exact validation failure
        tampered_brief = build_content_brief(cand)
        tampered_brief["recommended_internal_links"][2]["anchor_el"] += " ALTERED"
        tampered_errors = qa._validate_content_brief_compliance(markdown, "Dentplant", "Dentplant", tampered_brief)
        self.assertTrue(any("Internal-link anchors 3 are not aligned with the ContentBrief." in e for e in tampered_errors))

        with self.assertRaises(LinkPlanValidationError):
            validate_link_plan(parsed, tampered_brief)


if __name__ == "__main__":
    unittest.main()
