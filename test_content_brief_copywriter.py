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


if __name__ == "__main__":
    unittest.main()
