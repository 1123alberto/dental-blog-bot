import json
import tempfile
import unittest
from pathlib import Path

from agents.clinical_review import (
    AUTOMATED_DRAFT,
    CLINICAL_REVIEW_REQUIRED,
    CLINICALLY_REVIEWED,
    attribution_for,
    classify_clinical_review,
    mark_clinically_reviewed,
    save_review_record,
)
from agents.qa_agent import QAAgent


def brief(**overrides):
    value = {
        "candidate_title": "Routine preventive dental guidance",
        "primary_patient_intent": "general oral-health education",
        "evidence_maturity": "established clinical practice",
        "claims": [{"claim": "Regular preventive visits support oral health.", "evidence_excerpt": "Regular preventive visits support oral health."}],
        "clinical_risk_topic": False,
        "recommended_internal_links": [],
    }
    value.update(overrides)
    return value


class TestClinicalReviewStatus(unittest.TestCase):
    def test_ordinary_article_is_automated_draft_and_qa_is_not_a_review(self):
        status = classify_clinical_review(brief())
        self.assertEqual(status["status"], AUTOMATED_DRAFT)
        self.assertIsNone(status["reviewer"])
        self.assertNotIn("reviewed", attribution_for(status, "en").lower())

    def test_complications_early_research_and_oral_systemic_topics_trigger_review(self):
        complication = classify_clinical_review(brief(primary_patient_intent="risks/complications", clinical_risk_topic=True))
        early = classify_clinical_review(brief(evidence_maturity="early research"))
        systemic = classify_clinical_review(brief(candidate_title="Diabetes and periodontal disease association"))
        for status in (complication, early, systemic):
            self.assertEqual(status["status"], CLINICAL_REVIEW_REQUIRED)
        self.assertIn("clinical_risk_topic", complication["review_required_reasons"])
        self.assertIn("early_research", early["review_required_reasons"])
        self.assertIn("oral_systemic_association", systemic["review_required_reasons"])

    def test_manual_review_requires_identity_and_timestamp_and_uses_correct_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.json"
            record = mark_clinically_reviewed("article-1", "Dr. Angelo Moshopoulos", "2026-08-13T12:00:00+00:00", path)
            self.assertEqual(record["status"], CLINICALLY_REVIEWED)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["reviewer"], "Dr. Angelo Moshopoulos")
        with self.assertRaises(ValueError):
            mark_clinically_reviewed("article-1", "Δρ. Άγγελος Μοσχόπουλος", "2026-08-13T12:00:00+00:00")
        reviewed = {"status": CLINICALLY_REVIEWED}
        self.assertIn("Dr. Angelo Moshopoulos", attribution_for(reviewed, "en"))
        self.assertIn("κ. Άγγελο Μοσχόπουλο", attribution_for(reviewed, "el"))
        self.assertNotIn("Δρ.", attribution_for(reviewed, "el"))

    def test_record_is_compact_and_contains_no_article_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.json"
            save_review_record({
                **classify_clinical_review(brief()),
                "raw_body": "must never be persisted",
            }, path)
            self.assertNotIn("raw_body", path.read_text(encoding="utf-8"))


class TestMedicalQASafeguards(unittest.TestCase):
    def setUp(self):
        self.qa = QAAgent()

    def errors(self, text, content_brief=None):
        return self.qa._validate_content_brief_compliance("", text, "", content_brief or brief())

    def test_statistics_and_absolute_claims_are_checked(self):
        self.assertTrue(any("Unsupported statistic" in e for e in self.errors("Success is 99%.")))
        supported = brief(claims=[{"claim": "Success was 99%.", "evidence_excerpt": "Success was 99%."}])
        self.assertFalse(any("Unsupported statistic" in e for e in self.errors("Success is 99%.", supported)))
        self.assertTrue(any("Absolute" in e for e in self.errors("This guaranteed, zero-risk treatment is completely painless.")))
        self.assertTrue(any("Absolute" in e for e in self.errors("Η θεραπεία έχει μηδενικό κίνδυνο και είναι εντελώς ανώδυνη.")))

    def test_causation_emerging_care_and_availability_are_checked(self):
        self.assertTrue(any("causation" in e for e in self.errors("Diabetes directly causes periodontal disease.")))
        emerging = brief(evidence_maturity="emerging clinical adoption")
        self.assertTrue(any("standard or routine" in e for e in self.errors("This is standard treatment.", emerging)))
        self.assertTrue(any("availability" in e for e in self.errors("Dentplant offers robotic implant surgery.")))


if __name__ == "__main__":
    unittest.main()
