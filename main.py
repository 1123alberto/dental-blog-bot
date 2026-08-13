import os
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Reconfigure stdout and stderr to support UTF-8 and handle encoding errors gracefully
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')

from generator import evaluate_article_candidates, generate_blog_post_from_evaluation
from publisher import publish_blog_post, WEBSITE_DATA_PATH, load_merged_posts
from scraper import fetch_dental_news
from agents import log_group_start, log_group_end
from agents.content_decision_agent import (
    ContentDecisionAgent,
    DECISION_CREATE,
    DECISION_SKIP,
    DECISION_UPDATE,
)
from agents.content_brief import build_content_brief
from agents.clinical_review import classify_clinical_review, save_review_record
from approval_gate import CLINICAL_REVIEW_PR, NO_PUBLICATION, draft_pr_body, publication_plan
from publisher import parse_bilingual_content
from version import PRODUCT_NAME, __version__


WEEKLY_DECISION_PATH = Path(__file__).resolve().parent / "output" / "weekly_decision.json"
WEEKLY_CONTENT_BRIEF_PATH = Path(__file__).resolve().parent / "output" / "weekly_content_brief.json"
WEEKLY_CLINICAL_REVIEW_PATH = Path(__file__).resolve().parent / "output" / "weekly_clinical_review.json"
VALID_DECISIONS = {DECISION_CREATE, DECISION_UPDATE, DECISION_SKIP}
RUNTIME_ACTIONS = {
    DECISION_CREATE: "article_generation_started",
    DECISION_UPDATE: "existing_page_update_recommended",
    DECISION_SKIP: "publication_skipped",
}


def validate_weekly_decision(decision):
    if not isinstance(decision, dict) or decision.get("decision") not in VALID_DECISIONS:
        raise RuntimeError("Content decision is missing or contains an unknown decision value.")
    if not isinstance(decision.get("reasons"), list):
        raise RuntimeError("Content decision is malformed: reasons must be a list.")
    if decision["decision"] == DECISION_UPDATE and not decision.get("recommended_target_page"):
        raise RuntimeError("Content decision is malformed: an update requires a target page.")


def save_weekly_decision(decision, runtime_action, publication=None, output_path=None):
    """Persist a compact, safe-to-commit record; never include raw source article bodies."""
    snapshot = decision.get("candidate_snapshot") or None
    if snapshot:
        allowed_snapshot_fields = {
            "title", "source", "category", "editorial_score", "strategic_scores", "strategic_value",
            "final_score", "related_dentplant_pages", "clinical_risk_topic", "is_promotional",
            "is_low_quality", "is_us_centric",
        }
        snapshot = {key: value for key, value in snapshot.items() if key in allowed_snapshot_fields}
    record = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision["decision"],
        "candidate_title": decision.get("candidate_title"),
        "recommended_target_page": decision.get("recommended_target_page"),
        "decision_score": decision.get("decision_score"),
        "reasons": decision.get("reasons", []),
        "candidate_snapshot": snapshot,
        "candidate_rank": decision.get("candidate_rank"),
        "evaluated_candidate_count": decision.get("evaluated_candidate_count"),
        "action_scores": decision.get("action_scores"),
        "runtime_action": runtime_action,
        "publication_action": (publication or {}).get("publication_action", NO_PUBLICATION),
        "article_id": (publication or {}).get("article_id"),
        "review_branch": (publication or {}).get("review_branch"),
        "review_reasons": (publication or {}).get("review_reasons", []),
        "draft_pr_title": (publication or {}).get("draft_pr_title"),
        "draft_pr_body": (publication or {}).get("draft_pr_body"),
    }
    output_path = Path(output_path or WEEKLY_DECISION_PATH)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def save_weekly_content_brief(brief, output_path=None):
    """Persist the compact source/strategy brief only for a new-article action."""
    output_path = Path(output_path or WEEKLY_CONTENT_BRIEF_PATH)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return brief


def main():
    if "--dashboard" in sys.argv:
        print(f"Starting {PRODUCT_NAME} v{__version__} dashboard on http://127.0.0.1:8000...")
        import uvicorn
        uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
        return

    log_group_start("[1] Fetching latest dental journal news & extracting article text")
    news_items = fetch_dental_news()
    log_group_end()

    if not news_items:
        print("No news found. Exiting.")
        return

    print(f"Fetched {len(news_items)} total entries from dental feeds.")

    # Load publication history to prevent duplicate topics
    recent_titles = []
    try:
        posts = load_merged_posts()
        # Extract titles of the last 10 published posts
        for post in posts[:10]:
            title = post.get("en", {}).get("title")
            if title:
                recent_titles.append(title)
        print(f"Loaded {len(recent_titles)} recently published article titles for topic avoidance:")
        for title in recent_titles:
            print(f"  - {title}")
    except Exception as e:
        print(f"Warning: Could not load publication history: {e}")

    evaluation = evaluate_article_candidates(news_items, recent_posts=recent_titles, for_weekly_decision=True)
    if not evaluation:
        raise RuntimeError("Editorial evaluation did not return a candidate.")

    decision = ContentDecisionAgent().decide(evaluation["candidates"])
    validate_weekly_decision(decision)
    runtime_action = RUNTIME_ACTIONS[decision["decision"]]
    save_weekly_decision(decision, runtime_action)
    print(f"[Weekly Decision] {decision['decision']}: {decision['reasons'][0]}")

    if decision["decision"] == DECISION_UPDATE:
        print(f"[Weekly Decision] Advisory only; recommended target: {decision['recommended_target_page']}")
        return
    if decision["decision"] == DECISION_SKIP:
        print("[Weekly Decision] Intentional skip; no content will be generated or published.")
        return

    candidate_rank = decision.get("candidate_rank")
    if not isinstance(candidate_rank, int) or not 1 <= candidate_rank <= len(evaluation["candidates"]):
        raise RuntimeError("Content decision is malformed: chosen candidate rank is invalid.")
    chosen_candidate = evaluation["candidates"][candidate_rank - 1]
    if chosen_candidate.get("title") != decision.get("candidate_title"):
        raise RuntimeError("Content decision is malformed: chosen candidate does not match its title.")
    evaluation = {**evaluation, "best_candidate": chosen_candidate}
    brief = build_content_brief(chosen_candidate, recent_titles=recent_titles)
    save_weekly_content_brief(brief)
    evaluation = {**evaluation, "content_brief": brief}
    print(f"[Content Brief] Persisted source/strategy brief for: {brief['candidate_title']}")

    print("[3] Starting existing article generation pipeline...")
    blog_markdown = generate_blog_post_from_evaluation(evaluation, practice_name="Dentplant")

    if blog_markdown.startswith("Error"):
        print(f"CRITICAL ERROR: {blog_markdown}")
        sys.exit(1)

    # This classification is deliberately independent of automated QA.  It records
    # a recommendation, not a completed clinician review or a publishing block.
    review_status = classify_clinical_review(brief, blog_markdown)
    save_review_record(review_status, WEEKLY_CLINICAL_REVIEW_PATH)
    plan = publication_plan(review_status)
    if plan["publication_action"] == CLINICAL_REVIEW_PR:
        titles = parse_bilingual_content(blog_markdown)
        plan["draft_pr_title"] = f"Clinical review: {brief.get('candidate_title') or plan['article_id']}"
        plan["draft_pr_body"] = draft_pr_body(
            brief, {"en": titles["en"]["title"], "el": titles["el"]["title"]}, plan
        )
    save_weekly_decision(decision, runtime_action, publication=plan)
    print(f"[Clinical Review] {review_status['status']}: {', '.join(review_status['review_required_reasons']) or 'no trigger'}")
    print(f"[Publication] {plan['publication_action']}")

    log_group_start("[5] Publishing to output folder")
    file_path = publish_blog_post(
        blog_markdown,
        content_brief=evaluation.get("content_brief"),
        review_status=review_status,
    )
    log_group_end()

    if file_path:
        filename = os.path.basename(file_path)
        print(f"\n" + "="*50)
        print(f"SUCCESS!")
        print(f"Post: {filename}")
        print(f"Path: {file_path}")
        print("="*50 + "\n")
    else:
        print("Failed to publish blog post.")
        sys.exit(1)


if __name__ == "__main__":
    main()
