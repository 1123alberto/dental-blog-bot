"""Deterministic weekly content decisions based on evaluated editorial candidates.

This module is intentionally not wired into publishing. It makes a recommendation
that a later milestone may use to change workflow behavior.
"""

from __future__ import annotations

import json
from pathlib import Path


CONTENT_MAP_PATH = Path(__file__).resolve().parent.parent / "data" / "dentplant_content_map.json"

# Scores use the 1-10 dimensions introduced by the strategic editorial evaluation.
MIN_EDITORIAL_QUALITY = 30
MIN_STRATEGIC_VALUE = 32
MIN_CREATE_CONTENT_GAP = 6
MAX_CREATE_CANNIBALIZATION = 4
MIN_CREATE_SERVICE_RELEVANCE = 6
MIN_CREATE_PATIENT_INTENT = 6
UPDATE_CANNIBALIZATION_THRESHOLD = 5
UPDATE_MAX_CONTENT_GAP = 5
MIN_UPDATE_SERVICE_RELEVANCE = 7
MIN_UPDATE_CLUSTER_CONTRIBUTION = 7
MIN_UPDATE_PATIENT_INTENT = 6

# Action comparison weights. They intentionally reward distinct content and high-value
# updates differently, so the editorially first candidate is not automatically chosen.
CREATE_EDITORIAL_WEIGHT = 0.6
CREATE_STRATEGIC_WEIGHT = 0.6
CREATE_GAP_WEIGHT = 2.0
CREATE_LOW_CANNIBALIZATION_WEIGHT = 1.0
UPDATE_EDITORIAL_WEIGHT = 0.4
UPDATE_SERVICE_WEIGHT = 2.0
UPDATE_CLUSTER_WEIGHT = 2.0
UPDATE_INTENT_WEIGHT = 2.0
UPDATE_CANNIBALIZATION_WEIGHT = 2.0
UPDATE_LOW_GAP_WEIGHT = 1.5
UPDATE_TARGET_MATCH_BONUS = 5.0
SEARCH_CREATE_WEIGHT = 1.2
SEARCH_UPDATE_WEIGHT = 2.0
MIN_SEARCH_UPDATE_OPPORTUNITY = 4

DECISION_CREATE = "CREATE_NEW_ARTICLE"
DECISION_UPDATE = "UPDATE_EXISTING_PAGE"
DECISION_SKIP = "SKIP_THIS_WEEK"


def load_content_map(path=CONTENT_MAP_PATH):
    """Load content-map pages, returning an empty map if the inventory is unavailable."""
    try:
        with Path(path).open(encoding="utf-8") as handle:
            content_map = json.load(handle)
        pages = content_map.get("pages", [])
        if not isinstance(pages, list):
            raise ValueError("pages must be a list")
        return content_map
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ContentDecisionAgent] Content map unavailable: {exc}.")
        return {"pages": []}


def _editorial_quality(candidate):
    if "editorial_score" in candidate:
        return float(candidate["editorial_score"])
    return float(sum(candidate.get("scores", {}).values()))


def _strategic_scores(candidate):
    scores = candidate.get("strategic_scores") or {}
    return {
        "cluster_contribution": float(scores.get("cluster_contribution", 0)),
        "service_relevance": float(scores.get("service_relevance", 0)),
        "patient_intent_fit": float(scores.get("patient_intent_fit", 0)),
        "content_gap_value": float(scores.get("content_gap_value", 0)),
        "internal_link_opportunity": float(scores.get("internal_link_opportunity", 0)),
        "cannibalization_risk": float(scores.get("cannibalization_risk", 0)),
    }


def _strategic_value(scores):
    return sum(scores[key] for key in scores if key != "cannibalization_risk")


def _candidate_snapshot(candidate, scores, editorial_quality):
    return {
        "title": candidate.get("title"),
        "source": candidate.get("source"),
        "category": candidate.get("category"),
        "editorial_score": editorial_quality,
        "strategic_scores": scores,
        "strategic_value": _strategic_value(scores),
        "final_score": candidate.get("final_score"),
        "related_dentplant_pages": list(candidate.get("related_dentplant_pages") or []),
        "clinical_risk_topic": bool(candidate.get("clinical_risk_topic", False)),
        "is_promotional": bool(candidate.get("is_promotional", False)),
        "is_low_quality": bool(candidate.get("is_low_quality", False)),
        "is_us_centric": bool(candidate.get("is_us_centric", False)),
        "search_console_scores": candidate.get("search_console_scores", {}),
        "matched_queries": list(candidate.get("matched_queries", []))[:5],
        "matched_search_pages": list(candidate.get("matched_search_pages", []))[:5],
    }


def _is_disqualified(candidate):
    return any(bool(candidate.get(flag, False)) for flag in ("is_promotional", "is_low_quality", "is_us_centric"))


def _target_page(candidate, pages):
    """Choose only a mapped, structurally relevant page from candidate evidence."""
    page_by_path = {page.get("path"): page for page in pages if page.get("path")}
    related = [path for path in candidate.get("related_dentplant_pages", []) if path in page_by_path]
    if not related:
        return None

    service_relevance = _strategic_scores(candidate)["service_relevance"]
    ranked = []
    for related_index, path in enumerate(related):
        page = page_by_path[path]
        page_type = page.get("page_type")
        structural_score = 0
        if service_relevance >= MIN_UPDATE_SERVICE_RELEVANCE:
            structural_score += {"treatment hub": 30, "treatment detail": 25, "informational article": 15}.get(page_type, 0)
        else:
            structural_score += {"informational article": 30, "news/blog article": 20, "treatment hub": 15, "treatment detail": 10}.get(page_type, 0)
        structural_score += min(float(page.get("inbound_link_count", 0)), 20) / 100
        ranked.append((structural_score, -related_index, path))
    return max(ranked)[2]


class ContentDecisionAgent:
    """Select CREATE, UPDATE, or SKIP deterministically from evaluated candidates."""

    def __init__(self, content_map=None):
        self.content_map = content_map if content_map is not None else load_content_map()

    def decide(self, candidates):
        candidates = list(candidates or [])
        if not candidates:
            return self._skip("No evaluated candidates were supplied.")

        proposals = []
        for input_index, candidate in enumerate(candidates):
            proposal = self._eligible_action(candidate, input_index, len(candidates))
            if proposal:
                proposals.append(proposal)
        if not proposals:
            return self._skip("No supplied candidate cleared editorial and Dentplant strategic thresholds.")

        # Deterministic tie breakers retain the supplied editorial rank before title.
        chosen = max(proposals, key=lambda proposal: (
            proposal["decision_score"],
            -proposal["candidate_rank"],
            proposal["candidate_title"] or "",
        ))
        return chosen

    def _eligible_action(self, candidate, input_index, candidate_count):
        scores = _strategic_scores(candidate)
        editorial_quality = _editorial_quality(candidate)
        snapshot = _candidate_snapshot(candidate, scores, editorial_quality)
        strategic_value = snapshot["strategic_value"]

        if _is_disqualified(candidate):
            return None
        if editorial_quality < MIN_EDITORIAL_QUALITY:
            return None

        target = _target_page(candidate, self.content_map.get("pages", []))
        search = candidate.get("search_console_scores") or {}
        existing_search = float(search.get("existing_page_opportunity", 0))
        update_signals = (
            scores["service_relevance"] >= MIN_UPDATE_SERVICE_RELEVANCE
            and scores["cluster_contribution"] >= MIN_UPDATE_CLUSTER_CONTRIBUTION
            and scores["patient_intent_fit"] >= MIN_UPDATE_PATIENT_INTENT
            and scores["cannibalization_risk"] >= UPDATE_CANNIBALIZATION_THRESHOLD
            and scores["content_gap_value"] <= UPDATE_MAX_CONTENT_GAP
        )
        update_signals = update_signals or (
            target is not None and existing_search >= MIN_SEARCH_UPDATE_OPPORTUNITY
            and scores["service_relevance"] >= MIN_UPDATE_SERVICE_RELEVANCE
            and scores["patient_intent_fit"] >= MIN_UPDATE_PATIENT_INTENT
            and scores["cannibalization_risk"] >= UPDATE_CANNIBALIZATION_THRESHOLD
        )
        if update_signals and target:
            update_score = (
                editorial_quality * UPDATE_EDITORIAL_WEIGHT
                + scores["service_relevance"] * UPDATE_SERVICE_WEIGHT
                + scores["cluster_contribution"] * UPDATE_CLUSTER_WEIGHT
                + scores["patient_intent_fit"] * UPDATE_INTENT_WEIGHT
                + scores["cannibalization_risk"] * UPDATE_CANNIBALIZATION_WEIGHT
                + (10 - scores["content_gap_value"]) * UPDATE_LOW_GAP_WEIGHT
                + UPDATE_TARGET_MATCH_BONUS
                + existing_search * SEARCH_UPDATE_WEIGHT
            )
        else:
            update_score = None

        create_signals = (
            strategic_value >= MIN_STRATEGIC_VALUE
            and scores["service_relevance"] >= MIN_CREATE_SERVICE_RELEVANCE
            and scores["patient_intent_fit"] >= MIN_CREATE_PATIENT_INTENT
            and scores["content_gap_value"] >= MIN_CREATE_CONTENT_GAP
            and scores["cannibalization_risk"] <= MAX_CREATE_CANNIBALIZATION
        )
        if create_signals:
            create_score = (
                editorial_quality * CREATE_EDITORIAL_WEIGHT
                + strategic_value * CREATE_STRATEGIC_WEIGHT
                + scores["content_gap_value"] * CREATE_GAP_WEIGHT
                + (10 - scores["cannibalization_risk"]) * CREATE_LOW_CANNIBALIZATION_WEIGHT
                + (float(search.get("search_demand", 0)) + float(search.get("ctr_opportunity", 0)) + float(search.get("ranking_opportunity", 0))) * SEARCH_CREATE_WEIGHT
            )
        else:
            create_score = None

        action_scores = {"create": create_score, "update": update_score}
        if update_score is None and create_score is None:
            return None
        if update_score is not None and (create_score is None or update_score > create_score):
            return {
                "decision": DECISION_UPDATE,
                "candidate_title": candidate.get("title"),
                "recommended_target_page": target,
                "decision_score": round(update_score, 2),
                "reasons": [
                    "The topic strongly matches an existing Dentplant service cluster and patient intent.",
                    f"Cannibalization risk {scores['cannibalization_risk']:.1f} with content gap {scores['content_gap_value']:.1f} favors improving an existing page.",
                    f"Selected mapped target '{target}' using related-page and page-type evidence.",
                    f"Search Console existing-page opportunity is {existing_search:.1f}.",
                ],
                "candidate_snapshot": snapshot,
                "candidate_rank": input_index + 1,
                "evaluated_candidate_count": candidate_count,
                "action_scores": {key: round(value, 2) if value is not None else None for key, value in action_scores.items()},
            }
        if create_score is not None:
            return {
                "decision": DECISION_CREATE,
                "candidate_title": candidate.get("title"),
                "recommended_target_page": None,
                "decision_score": round(create_score, 2),
                "reasons": [
                    "The candidate clears editorial, strategic, patient-intent, and content-gap thresholds.",
                    f"Cannibalization risk {scores['cannibalization_risk']:.1f} is within the new-content limit of {MAX_CREATE_CANNIBALIZATION}.",
                    f"Search Console demand/opportunity contributes {float(search.get('search_demand', 0)):.1f}/{float(search.get('ranking_opportunity', 0)):.1f}.",
                ],
                "candidate_snapshot": snapshot,
                "candidate_rank": input_index + 1,
                "evaluated_candidate_count": candidate_count,
                "action_scores": {key: round(value, 2) if value is not None else None for key, value in action_scores.items()},
            }

    def _skip(self, reason, snapshot=None):
        return {
            "decision": DECISION_SKIP,
            "candidate_title": snapshot.get("title") if snapshot else None,
            "recommended_target_page": None,
            "decision_score": 0.0,
            "reasons": [reason],
            "candidate_snapshot": snapshot,
            "candidate_rank": None,
            "evaluated_candidate_count": 0,
            "action_scores": {"create": None, "update": None},
        }
