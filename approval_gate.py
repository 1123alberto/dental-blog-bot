"""Pure, fail-closed publication handoff metadata for clinical-review articles."""
from __future__ import annotations

import re
from datetime import date

from agents.clinical_review import AUTOMATED_DRAFT, CLINICAL_REVIEW_REQUIRED

DIRECT_PUBLISH = "direct_publish"
CLINICAL_REVIEW_PR = "clinical_review_pr"
NO_PUBLICATION = "none"


def review_branch_name(article_id, today=None):
    """Stable branch name; no user/source text can escape the branch namespace."""
    stamp = (today or date.today()).isoformat()
    slug = re.sub(r"[^a-z0-9]+", "-", str(article_id or "article").lower()).strip("-")
    slug = (slug or "article")[:72].rstrip("-")
    return f"clinical-review/blog-{stamp}-{slug}"


def publication_plan(review_status, today=None):
    status = (review_status or {}).get("status")
    if status == AUTOMATED_DRAFT:
        return {"publication_action": DIRECT_PUBLISH, "article_id": review_status.get("article_id"), "review_branch": None, "review_reasons": []}
    if status == CLINICAL_REVIEW_REQUIRED:
        article_id = review_status.get("article_id")
        if not article_id or not isinstance(review_status.get("review_required_reasons"), list):
            raise ValueError("Clinical-review metadata is incomplete; refusing publication handoff.")
        return {
            "publication_action": CLINICAL_REVIEW_PR,
            "article_id": article_id,
            "review_branch": review_branch_name(article_id, today),
            "review_reasons": list(review_status["review_required_reasons"]),
        }
    raise ValueError("Only automated_draft or clinical_review_required may enter publication.")


def draft_pr_body(brief, article_titles, plan):
    """Compact review metadata only—never article body, prompts, or credentials."""
    source = (brief or {}).get("source", {})
    claims = [str(item.get("claim", ""))[:280] for item in (brief or {}).get("claims", []) if item.get("claim")]
    links = [item.get("target_path") for item in (brief or {}).get("recommended_internal_links", []) if item.get("target_path")]
    numeric = any(re.search(r"\d+(?:[.,]\d+)?\s*%", claim) for claim in claims)
    lines = [
        "## Clinical review required",
        f"- Article: {brief.get('candidate_title') or plan.get('article_id')}",
        f"- English title: {article_titles.get('en') or 'Not available'}",
        f"- Greek title: {article_titles.get('el') or 'Not available'}",
        f"- Source: {source.get('name') or 'Not available'} ({source.get('published_date') or 'date unavailable'})",
        "- Dentplant publication target: `master`",
        f"- Review reasons: {', '.join(plan.get('review_reasons') or [])}",
        f"- Evidence maturity: {brief.get('evidence_maturity') or 'Not specified'}",
        f"- Supported claims requiring attention: {'; '.join(claims) or 'None listed'}",
        f"- Planned internal links: {', '.join(links) or 'None'}",
        f"- Numeric/statistical claims present: {'yes' if numeric else 'no'}",
        "",
        "Merge this PR only after clinical review is complete.",
    ]
    return "\n".join(lines)
