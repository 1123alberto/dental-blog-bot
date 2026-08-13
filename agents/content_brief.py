"""Deterministic ContentBrief planning for approved new Dentplant articles.

It works only with already-fetched candidate metadata and the generated content map.
It never refetches sources, modifies site content, or inserts HTML links.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


CONTENT_MAP_PATH = Path(__file__).resolve().parent.parent / "data" / "dentplant_content_map.json"
MAX_CLAIMS = 3
MAX_EVIDENCE_EXCERPT_LENGTH = 280
MAX_RELATED_PAGES = 5
INTENT_RULES = (
    ("risks/complications", ("risk", "complication", "failure", "infection", "loss", "loosening", "peri-implant")),
    ("recovery", ("recovery", "healing", "aftercare", "post-operative", "postoperative")),
    ("maintenance", ("maintenance", "care", "follow-up", "hygiene", "retention")),
    ("candidacy", ("candidate", "candidacy", "suitable", "eligib")),
    ("alternatives/comparison", ("alternative", "versus", "vs", "comparison", "compare")),
    ("long-term outcomes", ("long-term", "outcome", "durability", "survival")),
    ("prevention", ("prevent", "prevention", "reduce risk")),
    ("diagnosis", ("diagnos", "detect", "screen", "imaging")),
    ("treatment education", ("treatment", "procedure", "implant", "aligner", "veneer", "whitening")),
    ("research/innovation", ("study", "research", "trial", "innovation", "new", "emerging")),
)
CLUSTER_TERMS = {
    "implants": ("implant", "osseointegration", "abutment", "bone graft", "sinus lift", "all-on-4", "titanium"),
    "clear aligners": ("aligner", "orthodont", "braces", "retention"),
    "aesthetic dentistry": ("veneer", "whitening", "bleaching", "cosmetic", "aesthetic", "smile"),
    "periodontology": ("periodont", "gum", "gingiv", "plaque", "floss"),
    "endodontics": ("endodont", "root canal"),
    "prevention": ("prevent", "fluoride", "hygiene", "brush", "sealant"),
}
RISK_TERMS = ("risk", "complication", "failure", "infection", "loss", "loosening", "peri-implant", "titanium particles")
ENGLISH_ANCHORS = {
    "implants.html": "dental implant treatment",
    "implant-single-tooth.html": "single-tooth dental implants",
    "implant-all-on-4.html": "All-on-4 dental implants",
    "implant-full-arch.html": "full-arch dental implants",
    "implant-immediate-loading.html": "immediate-loading dental implants",
    "implant-mini.html": "mini dental implants",
    "article-timeline.html": "the dental implant treatment process",
    "clear-aligners.html": "clear aligner treatment",
    "teeth-whitening.html": "teeth whitening treatment",
    "porcelain-veneers.html": "porcelain veneers",
}


def load_content_map(path=CONTENT_MAP_PATH):
    with Path(path).open(encoding="utf-8") as handle:
        content_map = json.load(handle)
    if not isinstance(content_map.get("pages"), list):
        raise ValueError("Content map pages must be a list")
    return content_map


def _clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _sentences(text):
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", _clean_text(text)) if sentence.strip()]


def _cluster(candidate):
    text = " ".join(str(candidate.get(key, "")) for key in ("title", "summary", "full_text", "category")).lower()
    matches = [(sum(term in text for term in terms), name) for name, terms in CLUSTER_TERMS.items()]
    count, name = max(matches, default=(0, "general dentistry"))
    return name if count else "general dentistry"


def _intents(candidate):
    text = " ".join(str(candidate.get(key, "")) for key in ("title", "summary", "full_text")).lower()
    matches = [intent for intent, terms in INTENT_RULES if any(term in text for term in terms)]
    primary = matches[0] if matches else "general oral-health education"
    return primary, matches[1:3]


def _evidence_maturity(candidate):
    text = " ".join(str(candidate.get(key, "")) for key in ("title", "summary", "full_text")).lower()
    if any(term in text for term in ("in vitro", "laboratory", "animal model", "preclinical", "cell culture")):
        return "laboratory/preclinical research"
    if any(term in text for term in ("pilot study", "early study", "first-in-human", "feasibility", "prototype")):
        return "early research"
    if any(term in text for term in ("emerging", "new technology", "innovation", "novel")):
        return "emerging clinical adoption"
    if any(term in text for term in ("systematic review", "meta-analysis", "guideline", "randomized", "clinical trial")):
        return "established evidence but context-dependent use"
    return "established clinical practice"


def _claims(candidate):
    source_text = _clean_text(candidate.get("summary")) or _clean_text(candidate.get("full_text"))
    claims = []
    for sentence in _sentences(source_text)[:MAX_CLAIMS]:
        excerpt = sentence[:MAX_EVIDENCE_EXCERPT_LENGTH].rstrip()
        if not excerpt:
            continue
        confidence = "high" if len(excerpt.split()) >= 8 else "medium"
        claims.append({"claim": excerpt, "support": "source", "evidence_excerpt": excerpt, "confidence": confidence})
    return claims


def _page_by_path(content_map):
    return {page.get("path"): page for page in content_map["pages"] if page.get("path")}


def _page_cluster_match(page, cluster):
    text = " ".join([page.get("path", ""), page.get("title", ""), *page.get("h1", [])]).lower()
    return any(term in text for term in CLUSTER_TERMS.get(cluster, ()))


def _select_related_pages(candidate, content_map, cluster):
    by_path = _page_by_path(content_map)
    related = [path for path in candidate.get("related_dentplant_pages", []) if path in by_path]
    if not related:
        related = [path for path, page in by_path.items() if _page_cluster_match(page, cluster)]
    ranked = []
    for index, path in enumerate(related):
        page = by_path[path]
        page_type = page.get("page_type")
        type_score = {"treatment hub": 30, "treatment detail": 25, "informational article": 20, "news/blog article": 10}.get(page_type, 0)
        ranked.append((type_score + min(page.get("inbound_link_count", 0), 20) / 100, -index, path))
    return [entry[2] for entry in sorted(ranked, reverse=True)[:MAX_RELATED_PAGES]]


def _anchor_for_page(page, used_anchors):
    english = ENGLISH_ANCHORS.get(page["path"]) or page["path"].replace(".html", "").replace("-", " ")
    greek = _clean_text(" ".join(page.get("h1", []))) or english
    base_en = english[:90]
    base_el = greek[:90]
    suffix = 2
    while base_en.lower() in used_anchors:
        base_en = f"{english[:80]} ({suffix})"
        suffix += 1
    used_anchors.add(base_en.lower())
    return base_en, base_el


def _recommended_links(paths, content_map):
    by_path = _page_by_path(content_map)
    used_anchors = set()
    links = []
    for index, path in enumerate(paths[:5]):
        page = by_path[path]
        anchor_en, anchor_el = _anchor_for_page(page, used_anchors)
        relationship = "primary treatment hub" if page.get("page_type") == "treatment hub" else "supporting Dentplant page"
        links.append({
            "target_path": path,
            "relationship": relationship,
            "anchor_en": anchor_en,
            "anchor_el": anchor_el,
            "reason": f"Mapped page is structurally relevant to the planned {relationship} context.",
        })
    return links


def _duplication_avoidance(candidate, related_paths, content_map):
    by_path = _page_by_path(content_map)
    guidance = []
    for path in related_paths[:3]:
        page = by_path[path]
        heading = next(iter(page.get("h1", [])), page.get("title", path))
        guidance.append(f"Do not recreate the broad scope of '{heading}' ({path}); add a narrower source-supported angle.")
    risk = (candidate.get("strategic_scores") or {}).get("cannibalization_risk", 0)
    if risk >= 5:
        guidance.append("Avoid competing for the same core intent; focus on a distinct question, context, or patient decision point.")
    return guidance or ["Avoid generic treatment overviews and focus on the candidate's source-supported incremental value."]


def _risk_notes(candidate):
    text = " ".join(str(candidate.get(key, "")) for key in ("title", "summary", "full_text")).lower()
    if not candidate.get("clinical_risk_topic") and not any(term in text for term in RISK_TERMS):
        return []
    return [
        "Describe risks proportionately; do not present risk as inevitability.",
        "Distinguish evidence-supported warning signs or prevention from unsupported generalizations.",
        "Do not imply zero-risk treatment or add unsupported outcome percentages.",
    ]


def build_content_brief(candidate, recent_titles=None, content_map=None):
    """Build a compact, deterministic brief from an already selected candidate."""
    content_map = content_map if content_map is not None else load_content_map()
    cluster = _cluster(candidate)
    primary_intent, secondary_intents = _intents(candidate)
    related_paths = _select_related_pages(candidate, content_map, cluster)
    claims = _claims(candidate)
    source = {
        "name": candidate.get("source") or None,
        "url": candidate.get("link") or candidate.get("url") or None,
        "published_date": candidate.get("date") or candidate.get("published_date") or None,
        "original_title": candidate.get("title") or None,
    }
    return {
        "schema_version": "1.0",
        "candidate_title": candidate.get("title") or None,
        "source": source,
        "article_angle": (claims[0]["claim"] if claims else candidate.get("title") or "Source-supported patient education"),
        "evidence_maturity": _evidence_maturity(candidate),
        "primary_patient_intent": primary_intent,
        "secondary_patient_intents": secondary_intents,
        "primary_cluster": cluster,
        "related_dentplant_pages": related_paths,
        "recommended_internal_links": _recommended_links(related_paths, content_map),
        "claims": claims,
        "clinical_risk_topic": bool(candidate.get("clinical_risk_topic")) or bool(_risk_notes(candidate)),
        "clinical_risk_notes": _risk_notes(candidate),
        "duplication_avoidance": _duplication_avoidance(candidate, related_paths, content_map),
        "editorial_constraints": [
            "Use only source-supported claims; do not add unsupported statistics or medical facts.",
            "Do not claim Dentplant offers a technology unless it is supported by existing site content.",
            "Do not claim superiority, guaranteed outcomes, painless treatment, or lifetime success.",
            "Use association language for observational oral-systemic evidence; do not convert association into causation.",
            "Do not describe early, preclinical, or emerging evidence as standard care or a routine clinical protocol.",
            "Patient education cannot diagnose, replace examination, or determine treatment candidacy.",
            "Do not invent practitioner credentials; keep Greek professional naming consistent with existing Dentplant conventions.",
            "Recommended internal links are planning guidance only; do not insert HTML links in this milestone.",
        ],
        "recent_publication_titles_considered": list(recent_titles or [])[:10],
    }
