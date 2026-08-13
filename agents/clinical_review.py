"""Deterministic clinical-review status and safe attribution for generated articles."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


AUTOMATED_DRAFT = "automated_draft"
CLINICAL_REVIEW_REQUIRED = "clinical_review_required"
CLINICALLY_REVIEWED = "clinically_reviewed"
VALID_STATUSES = {AUTOMATED_DRAFT, CLINICAL_REVIEW_REQUIRED, CLINICALLY_REVIEWED}
ENGLISH_REVIEWER = "Dr. Angelo Moshopoulos"
GREEK_REVIEWER = "κ. Άγγελος Μοσχόπουλος"
REVIEW_RECORD_PATH = Path(__file__).resolve().parent.parent / "output" / "weekly_clinical_review.json"


def article_id_for(content_brief):
    """Stable, non-sensitive identifier suitable for a compact review record."""
    title = str((content_brief or {}).get("candidate_title") or "generated-article").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", title).strip("-")
    return slug or "generated-article"


def _text(content_brief, markdown_content=""):
    claims = " ".join(str(item.get("claim", "")) for item in (content_brief or {}).get("claims", []))
    return " ".join((str((content_brief or {}).get("candidate_title", "")), claims, str(markdown_content or ""))).lower()


def classify_clinical_review(content_brief, markdown_content=""):
    """Return an inspectable status; automated QA is intentionally not an input."""
    brief = content_brief or {}
    text = _text(brief, markdown_content)
    reasons = []
    if brief.get("clinical_risk_topic") or brief.get("primary_patient_intent") == "risks/complications" or any(
        term in text for term in ("implant failure", "peri-implantitis", "periimplantitis", "complication", "treatment failure")
    ):
        reasons.append("clinical_risk_topic")
    if brief.get("evidence_maturity") in {"early research", "laboratory/preclinical research", "emerging clinical adoption"}:
        reasons.append("early_research")
    if re.search(r"\b\d+(?:[.,]\d+)?\s*(?:%|percent|ποσοστ)", text, re.IGNORECASE):
        reasons.append("numeric_outcome_claim")
    if any(term in text for term in ("diabetes", "cardiovascular", "heart disease", "systemic disease", "oral-systemic", "διαβήτη", "καρδιαγγεια", "συστηματικ")):
        reasons.append("oral_systemic_association")
    if brief.get("primary_patient_intent") == "diagnosis" and brief.get("evidence_maturity") != "established clinical practice":
        reasons.append("diagnostic_innovation")
    if any(term in text for term in ("treatment outcome", "survival rate", "success rate", "κλινικό αποτέλεσμα", "ποσοστό επιτυχίας")):
        reasons.append("treatment_outcome_claim")
    reasons = list(dict.fromkeys(reasons))
    return {
        "article_id": article_id_for(brief),
        "status": CLINICAL_REVIEW_REQUIRED if reasons else AUTOMATED_DRAFT,
        "review_required_reasons": reasons,
        "reviewer": None,
        "reviewed_at": None,
        "source": "automated_pipeline",
    }


def save_review_record(review_status, output_path=None):
    """Persist only review metadata, never article bodies, prompts, or credentials."""
    record = {key: review_status.get(key) for key in (
        "article_id", "status", "review_required_reasons", "reviewer", "reviewed_at", "source"
    )}
    if record["status"] not in VALID_STATUSES:
        raise ValueError("Unknown clinical review status.")
    path = Path(output_path or REVIEW_RECORD_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def mark_clinically_reviewed(article_id, reviewer, reviewed_at, output_path=None):
    """Explicit manual-only update utility; it never runs in the publication pipeline."""
    if reviewer not in {ENGLISH_REVIEWER, GREEK_REVIEWER}:
        raise ValueError("Reviewer identity must be an approved Dentplant clinician identity.")
    if not article_id or not reviewed_at:
        raise ValueError("article_id and reviewed_at are required for a clinical review record.")
    try:
        datetime.fromisoformat(str(reviewed_at).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("reviewed_at must be an ISO-8601 timestamp.") from exc
    record = {
        "article_id": article_id,
        "status": CLINICALLY_REVIEWED,
        "review_required_reasons": [],
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "source": "manual_clinical_review",
    }
    return save_review_record(record, output_path)


def attribution_for(review_status, language):
    """Patient-facing wording; never exposes internal status labels."""
    status = (review_status or {}).get("status", AUTOMATED_DRAFT)
    if status == CLINICALLY_REVIEWED:
        return "Clinically reviewed by Dr. Angelo Moshopoulos" if language == "en" else "Κλινικός έλεγχος από τον κ. Άγγελο Μοσχόπουλο"
    prepared = "Prepared by the Dentplant Editorial Team" if language == "en" else "Προετοιμάστηκε από τη Συντακτική Ομάδα της Dentplant"
    if status == CLINICAL_REVIEW_REQUIRED:
        return prepared + (" · Clinical review recommended" if language == "en" else " · Συνιστάται κλινικός έλεγχος")
    return prepared
