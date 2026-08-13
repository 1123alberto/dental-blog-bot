import re
import json
from pathlib import Path
from agents.base import BaseAgent
from search_console import opportunity_scores, query_relevance


CONTENT_MAP_PATH = Path(__file__).resolve().parent.parent / "data" / "dentplant_content_map.json"
STRATEGIC_SCORE_FIELDS = (
    "cluster_contribution",
    "service_relevance",
    "patient_intent_fit",
    "content_gap_value",
    "internal_link_opportunity",
    "cannibalization_risk",
)
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "with", "by", "of",
    "from", "about", "into", "over", "after", "is", "are", "was", "were", "be", "been", "being",
    "new", "study", "research", "report", "shows", "show", "latest", "dental", "dentistry",
}
SERVICE_CLUSTERS = {
    "implants": ("implant", "osseointegration", "abutment", "bone graft", "sinus lift", "all-on-4", "titanium"),
    "aligners": ("aligner", "orthodont", "braces", "retention"),
    "aesthetics": ("veneer", "whitening", "bleaching", "cosmetic", "aesthetic", "smile"),
    "periodontology": ("periodont", "gum", "gingiv", "plaque", "floss"),
    "endodontics": ("endodont", "root canal"),
    "prevention": ("prevent", "fluoride", "hygiene", "brush", "sealant"),
}
PATIENT_INTENT_TERMS = (
    "treatment", "candidate", "candidacy", "diagnos", "prevent", "recovery", "recover", "risk",
    "alternative", "maintenance", "long-term", "outcome", "cost", "pain", "care", "complication",
)
CLINICAL_RISK_TERMS = (
    "implant failure", "failure of implant", "implant infection", "implant loss", "failed implant",
    "loosening of implant", "failure rate", "titanium particles", "complication", "peri-implantitis",
)


def load_content_map(path=CONTENT_MAP_PATH):
    """Load the generated website inventory without making the editorial flow depend on it."""
    try:
        with Path(path).open(encoding="utf-8") as handle:
            content_map = json.load(handle)
        pages = content_map.get("pages", [])
        if not isinstance(pages, list):
            raise ValueError("pages must be a list")
        return content_map
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[EditorialAgent] Content map unavailable: {exc}. Using neutral strategic defaults.")
        return {"pages": []}


def _tokens(text):
    words = re.findall(r"[\w-]+", (text or "").lower().replace("-", " "))
    return {word for word in words if len(word) > 2 and word not in STOP_WORDS}


def _article_text(article):
    return " ".join(str(article.get(key, "")) for key in ("title", "summary", "full_text", "category"))


def _matching_clusters(text):
    text = text.lower()
    return [name for name, terms in SERVICE_CLUSTERS.items() if any(term in text for term in terms)]


def _page_text(page):
    return " ".join([
        page.get("path", ""), page.get("title", ""), *page.get("h1", []),
        *page.get("h2", []), *page.get("h3", []), page.get("page_type", ""),
    ])


def evaluate_dentplant_strategy(article, content_map=None):
    """Score observable fit with Dentplant's current pages; no external data is used."""
    content_map = content_map or load_content_map()
    pages = content_map.get("pages", [])
    text = _article_text(article)
    text_lower = text.lower()
    article_tokens = _tokens(text)
    clusters = _matching_clusters(text)
    clinical_risk_topic = any(term in text_lower for term in CLINICAL_RISK_TERMS)

    related = []
    for page in pages:
        page_tokens = _tokens(_page_text(page))
        overlap = len(article_tokens & page_tokens)
        union = len(article_tokens | page_tokens) or 1
        similarity = overlap / union
        path_lower = page.get("path", "").lower()
        cluster_match = any(cluster.rstrip("s") in path_lower or any(term in path_lower for term in SERVICE_CLUSTERS[cluster]) for cluster in clusters)
        if overlap or cluster_match:
            score = (
                similarity
                + (0.25 if cluster_match else 0)
                + (0.30 if page.get("page_type") == "treatment hub" else 0)
                + (0.05 if page.get("page_type") == "treatment detail" else 0)
            )
            related.append((score, page))
    related.sort(key=lambda item: (-item[0], item[1].get("path", "")))
    related_pages = [page.get("path") for _, page in related[:5]]
    best_similarity = related[0][0] if related else 0

    service_relevance = 2
    if clusters:
        service_relevance = 8 if any(page.get("is_treatment_page") for _, page in related) else 6
    cluster_contribution = 2 if not clusters else (8 if related_pages else 6)
    # Existing pages that substantially overlap in path/title/headings raise cannibalization and lower gap value.
    cannibalization_risk = min(10, round(best_similarity * 12)) if related else 0
    content_gap_value = max(1, 9 - cannibalization_risk + (1 if clusters else 0))
    intent_matches = sum(term in text_lower for term in PATIENT_INTENT_TERMS)
    patient_intent_fit = min(10, 4 + intent_matches * 2 + (2 if clusters else 0))
    internal_link_opportunity = min(10, len(related_pages) * 2)
    if clusters and internal_link_opportunity < 4:
        internal_link_opportunity = 4

    scores = {
        "cluster_contribution": cluster_contribution,
        "service_relevance": service_relevance,
        "patient_intent_fit": patient_intent_fit,
        "content_gap_value": content_gap_value,
        "internal_link_opportunity": internal_link_opportunity,
        "cannibalization_risk": cannibalization_risk,
    }
    reasoning = (
        f"Matched Dentplant clusters: {', '.join(clusters) if clusters else 'none'}; "
        f"related pages: {', '.join(related_pages) if related_pages else 'none'}; "
        f"best observable overlap: {best_similarity:.2f}."
    )
    return scores, related_pages, clinical_risk_topic, reasoning


def _add_search_console_evaluation(article, snapshot):
    neutral = {"search_demand": 0, "ctr_opportunity": 0, "ranking_opportunity": 0, "trend": 0, "existing_page_opportunity": 0}
    if not snapshot:
        article["search_console_scores"] = neutral
        article["matched_queries"] = []
        article["matched_search_pages"] = []
        article["search_console_reasoning"] = "Search Console performance signals unavailable; neutral scores used."
        return
    related = article.get("related_dentplant_pages", [])
    text = _article_text(article)
    matches = []
    for item in snapshot.get("queries", []):
        relevance = query_relevance(item.get("query"), text, related)
        if relevance >= 3:
            scores = opportunity_scores(item, item.get("previous"), relevance)
            matches.append((sum(scores.values()), relevance, item, scores))
    matches.sort(key=lambda item: (-item[0], -item[1], item[2]["query"]))
    top = matches[:5]
    if not top:
        article["search_console_scores"] = neutral; article["matched_queries"] = []; article["matched_search_pages"] = []
        article["search_console_reasoning"] = "No relevant Search Console queries matched this candidate."
        return
    aggregate = {key: _score_average([entry[3][key] for entry in top]) for key in neutral if key != "existing_page_opportunity"}
    mapped = [entry[2]["page"] for entry in top]
    existing = [entry for entry in top if entry[2]["page"] in related]
    aggregate["existing_page_opportunity"] = _score_average([
        (entry[3]["ctr_opportunity"] + entry[3]["ranking_opportunity"] + entry[3]["search_demand"]) / 3
        for entry in existing
    ]) if existing else 0
    article["search_console_scores"] = aggregate
    article["matched_queries"] = [{"query": entry[2]["query"], "page": entry[2]["page"], "impressions": entry[2]["impressions"]} for entry in top]
    article["matched_search_pages"] = list(dict.fromkeys(mapped))
    article["search_console_reasoning"] = f"Matched {len(top)} relevant query/page rows; existing-page opportunity {aggregate['existing_page_opportunity']:.1f}."


def _score_average(values):
    return round(sum(values) / len(values), 2) if values else 0


def add_strategic_evaluation(articles, content_map=None, search_console_snapshot=None):
    content_map = content_map or load_content_map()
    for article in articles:
        scores, related_pages, clinical_risk_topic, reasoning = evaluate_dentplant_strategy(article, content_map)
        article["strategic_scores"] = scores
        article["related_dentplant_pages"] = related_pages
        article["clinical_risk_topic"] = clinical_risk_topic
        article["strategic_reasoning"] = reasoning
        _add_search_console_evaluation(article, search_console_snapshot)
        # Retained for compatibility, but risk topics are never rejected solely for clinical subject matter.
        article["is_inappropriate"] = False
    return articles

def deduplicate_articles(articles):
    """
    Deduplication engine using Jaccard similarity on lowercased and stripped words in titles.
    If similarity > 0.35, they are duplicates. Keeps the best source tier / image.
    """
    def clean_title(title):
        if not title:
            return set()
        title = title.lower()
        title = re.sub(r'[^\w\s]', '', title)
        words = set(title.split())
        stop_words = {
            "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "with",
            "by", "of", "from", "up", "about", "into", "over", "after", "is", "are", "was",
            "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
            "new", "study", "research", "report", "show", "shows", "finds", "latest",
            "association", "journal"
        }
        return words - stop_words

    unique_groups = []
    
    for art in articles:
        words = clean_title(art.get("title", ""))
        matched_group = None
        for idx, group in enumerate(unique_groups):
            for member in group:
                member_words = clean_title(member.get("title", ""))
                if not words or not member_words:
                    continue
                intersection = words & member_words
                union = words | member_words
                similarity = len(intersection) / len(union) if union else 0
                if similarity > 0.35:
                    matched_group = idx
                    break
            if matched_group is not None:
                break
        
        if matched_group is not None:
            unique_groups[matched_group].append(art)
        else:
            unique_groups.append([art])

    representatives = []
    for group in unique_groups:
        if len(group) == 1:
            representatives.append(group[0])
            continue
        
        def get_source_tier(source_name):
            source_name = source_name.lower()
            t1_keywords = ["journal", "university", "clinical", "wiley", "nature", "science", "lancet", "periodontology"]
            t2_keywords = ["association", "ada", "tribune", "health", "today", "education"]
            if any(k in source_name for k in t1_keywords):
                return 1
            if any(k in source_name for k in t2_keywords):
                return 2
            return 3

        def sort_key(member):
            tier = get_source_tier(member.get("source", ""))
            has_image = 1 if member.get("image") else 0
            text_len = len(member.get("full_text", ""))
            return (tier, -has_image, -text_len)

        sorted_group = sorted(group, key=sort_key)
        representatives.append(sorted_group[0])

    print(f"Deduplicated {len(articles)} articles down to {len(representatives)} unique stories.")
    return representatives


def get_fallback_article_scores(art):
    return {
        "category": "General Dentistry",
        "scores": {
            "clinical_relevance": 5,
            "scientific_credibility": 5,
            "educational_value": 5,
            "innovation_significance": 5,
            "public_interest": 5,
            "practical_patient_relevance": 5
        },
        "is_promotional": False,
        "is_low_quality": False,
        "is_us_centric": False,
        "is_inappropriate": False,
        "clinical_risk_topic": False,
        "strategic_scores": {field: 0 for field in STRATEGIC_SCORE_FIELDS},
        "related_dentplant_pages": [],
        "strategic_reasoning": "Neutral strategic fallback score",
        "scoring_reasoning": "Fallback score"
    }


def heuristic_score_and_classify(articles, search_console_snapshot=None):
    """
    Fallback scorer in case of Gemini failures. Uses simple rule-based heuristics.
    """
    for art in articles:
        title = art.get("title", "").lower()
        summary = art.get("summary", "").lower()
        
        category = "General Dentistry"
        if any(k in title for k in ["implant", "screw", "abutment", "osseointegration"]):
            category = "Implantology"
        elif any(k in title for k in ["gum", "periodont", "gingiv", "floss", "plaque"]):
            category = "Periodontology"
        elif any(k in title for k in ["digital", "scanner", "cad/cam", "print", "3d", "software"]):
            category = "Digital dentistry"
        elif any(k in title for k in ["prevent", "brush", "fluoride", "sealant", "hygiene"]):
            category = "Preventive dentistry"
        elif any(k in title for k in ["whitening", "veneer", "cosmetic", "smile", "aesthetic"]):
            category = "Cosmetic dentistry"
        elif any(k in title for k in ["systemic", "heart", "diabetes", "body", "alzheimer", "overall health"]):
            category = "Oral-systemic health"
        elif any(k in title for k in ["minimally invasive", "laser", "conservative"]):
            category = "Minimally invasive dentistry"
        elif any(k in title for k in ["ai", "artificial intelligence", "deep learning", "machine learning"]):
            category = "AI with genuine clinical relevance"
        elif any(k in title for k in ["diagnos", "detect", "imaging", "x-ray", "cbct", "biomarker"]):
            category = "Diagnostic innovation"

        source = art.get("source", "").lower()
        base_score = 6
        if any(k in source for k in ["journal", "wiley", "nature", "science"]):
            base_score = 8
        elif any(k in source for k in ["tribune", "today", "health"]):
            base_score = 6
        else:
            base_score = 4

        is_promo = any(k in title or k in summary for k in ["acquires", "merger", "market size", "quarterly", "revenue", "agreement with", "partnership"])
        is_low = any(k in title or k in summary for k in ["celebrity", "shocking", "insane", "magic"])
        is_us = any(k in title or k in summary for k in ["medicaid", "medicare", "epa", "florida", "new york", "california", "congress", "senate", "ada proposes"])
        clinical_risk_topic = any(k in title or k in summary for k in CLINICAL_RISK_TERMS)

        art["category"] = category
        art["scores"] = {
            "clinical_relevance": base_score,
            "scientific_credibility": base_score + (1 if base_score > 6 else 0),
            "educational_value": base_score - 1,
            "innovation_significance": base_score,
            "public_interest": 5,
            "practical_patient_relevance": base_score - 1
        }
        art["is_promotional"] = is_promo
        art["is_low_quality"] = is_low
        art["is_us_centric"] = is_us
        art["is_inappropriate"] = False
        art["clinical_risk_topic"] = clinical_risk_topic
        art["scoring_reasoning"] = "Heuristically calculated"

    return add_strategic_evaluation(articles, search_console_snapshot=search_console_snapshot)


def score_image(article):
    """
    Scores the image URL of an article based on selection rules.
    """
    img_url = article.get("image")
    if not img_url:
        return 0

    img_url_lower = img_url.lower()
    
    blacklist_keywords = ["logo", "avatar", "icon", "placeholder", "badge", "ad-", "banner", "loader"]
    if any(k in img_url_lower for k in blacklist_keywords):
        return 0

    stock_keywords = ["stock", "shutterstock", "adobe", "depositphotos", "istock", "preview", "watermark", "generated"]
    if any(k in img_url_lower for k in stock_keywords):
        return 5

    source_lower = article.get("source", "").lower()
    t1_keywords = ["journal", "wiley", "nature", "science", "univ"]
    if any(k in img_url_lower or k in source_lower for k in t1_keywords):
        return 10

    return 8


def apply_history_filter(articles, recent_posts):
    """
    Penalizes articles that are too similar to recently published articles.
    """
    if not recent_posts:
        return articles

    def clean_text_words(text):
        if not text:
            return set()
        words = set(re.sub(r'[^\w\s]', '', text.lower()).split())
        stop_words = {"a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with", "of", "from"}
        return words - stop_words

    recent_words_list = [clean_text_words(title) for title in recent_posts]

    for art in articles:
        title = art.get("title", "")
        title_words = clean_text_words(title)
        
        penalty = 0
        max_similarity = 0
        
        for r_words in recent_words_list:
            if not title_words or not r_words:
                continue
            intersection = title_words & r_words
            union = title_words | r_words
            similarity = len(intersection) / len(union) if union else 0
            if similarity > max_similarity:
                max_similarity = similarity
        
        if max_similarity > 0.35:
            penalty += 40
        elif max_similarity > 0.2:
            penalty += 20
        
        art["history_penalty"] = penalty

    return articles


def get_top_3_candidates(articles):
    """
    Sorts articles by final score and returns the top 3 candidate articles.
    """
    for art in articles:
        editorial_scores = art.get("scores", {})
        strategic_scores = art.get("strategic_scores")
        # Legacy callers that provide pre-scored articles retain their historic total.
        editorial_component = sum(editorial_scores.values())
        strategic_component = 0
        cannibalization_penalty = 0
        if strategic_scores is not None:
            strategic_component = (
                strategic_scores.get("cluster_contribution", 0) * 1.5
                + strategic_scores.get("service_relevance", 0) * 1.5
                + strategic_scores.get("patient_intent_fit", 0) * 1.5
                + strategic_scores.get("content_gap_value", 0) * 1.5
                + strategic_scores.get("internal_link_opportunity", 0)
            )
            cannibalization_penalty = strategic_scores.get("cannibalization_risk", 0) * 2
        search = art.get("search_console_scores") or {}
        search_component = (search.get("search_demand", 0) * 1.2 + search.get("ctr_opportunity", 0)
                            + search.get("ranking_opportunity", 0) + max(0, search.get("trend", 0) - 5) * 0.5)
        img_score = score_image(art)
        art["image_score"] = img_score
        
        penalty = art.get("history_penalty", 0)
        if art.get("is_promotional"):
            penalty += 30
        if art.get("is_low_quality"):
            penalty += 25
        if art.get("is_us_centric"):
            penalty += 50
        # Clinical risk topics are useful patient education unless separate quality controls flag them.
            
        final_score = editorial_component + strategic_component + search_component + img_score - penalty - cannibalization_penalty
        art["editorial_score"] = editorial_component
        art["strategic_score"] = strategic_component
        art["search_console_score"] = search_component
        art["cannibalization_penalty"] = cannibalization_penalty
        art["final_score"] = final_score

    sorted_articles = sorted(articles, key=lambda x: x["final_score"], reverse=True)
    top_3 = sorted_articles[:3]
    
    print(f"Top 3 candidates chosen out of {len(articles)} articles:")
    for idx, art in enumerate(top_3):
        print(f"  [{idx}] Score: {art['final_score']} - Title: {art['title']} (Category: {art['category']})")
    
    return top_3


class EditorialAgent(BaseAgent):
    """
    EditorialAgent scores, categorizes, filters, and selects the single best
    article candidate for publication using editorial guidelines and history avoidance.
    """
    def __init__(self, client=None, model_name="gemini-3.5-flash", search_console_snapshot=None):
        super().__init__(client, model_name)
        self.search_console_snapshot = search_console_snapshot

    def score_and_select(self, articles, recent_posts, memory=None):
        """
        Runs the full editorial evaluation process.
        """
        print("[EditorialAgent] Evaluating articles...")
        if not articles:
            print("[EditorialAgent] No articles provided for evaluation.")
            return None

        top_3 = self.evaluate_candidates(articles, recent_posts)
        if not top_3:
            return None

        # Preserve the legacy single-candidate API and its final Gemini selection.
        return self.choose_best_candidate(top_3, recent_posts, memory)

    def evaluate_candidates(self, articles, recent_posts):
        """Return the top strategically scored candidates without a second selection call."""
        # 1. Deduplicate
        unique_articles = deduplicate_articles(articles)
        if not unique_articles:
            print("[EditorialAgent] All articles were deduplicated.")
            return None

        # 2. Score and Classify
        scored_articles = self.score_and_classify(unique_articles)

        # 3. Apply History Filter
        filtered_articles = apply_history_filter(scored_articles, recent_posts)

        # 4. Extract Top 3 Candidates
        top_3 = get_top_3_candidates(filtered_articles)
        if not top_3:
            print("[EditorialAgent] Failed to identify top 3 candidates.")
            return None

        return top_3

    def score_and_classify(self, articles):
        """
        Calls Gemini to score and categorize articles. Fallback to heuristics if API is unavailable.
        """
        if not self.client:
            print("[EditorialAgent] Warning: Gemini client not initialized. Using heuristic fallback scoring.")
            return heuristic_score_and_classify(articles, self.search_console_snapshot)

        articles_data = []
        for idx, art in enumerate(articles):
            articles_data.append({
                "index": idx,
                "title": art.get("title"),
                "source": art.get("source"),
                "summary": art.get("summary")[:300] if art.get("summary") else ""
            })

        system_instruction = (
            "You are an expert Dental Editorial Director. Analyze the provided dental news articles "
            "and output a structured JSON array detailing scores, category classification, and potential warning flags."
        )

        prompt = f"""
Analyze these {len(articles)} dental news articles.

For each article, you must:
1. Classify it into exactly one of these categories:
   - Implantology
   - Periodontology
   - Digital dentistry
   - Preventive dentistry
   - Cosmetic dentistry
   - Oral-systemic health
   - Minimally invasive dentistry
   - AI with genuine clinical relevance
   - Diagnostic innovation
   - General Dentistry
2. Score it from 1 to 10 on the following criteria:
   - clinical_relevance
   - scientific_credibility
   - educational_value
   - innovation_significance
   - public_interest
   - practical_patient_relevance
3. Identify if it contains elements we want to avoid:
   * is_promotional: true if it is a promotional press release, corporate/financial announcement, or low-value product advertisement.
   * is_us_centric: true if the topic is specifically about US insurance (Medicaid/Medicare), US litigation/EPA rulings, or US-specific administration that is not relevant to Europe.
   * is_low_quality: true if the article is sensationalist, misleading, unsupported, disproportionately alarmist, or clinically irrelevant. Clinically valid discussions of complications and treatment risks are allowed.
   * clinical_risk_topic: true when the article discusses treatment risks or complications. This is informational only and is not a rejection flag.

Return the response as a JSON array of objects.
Example format:
[
  {{
    "index": 0,
    "category": "Implantology",
    "clinical_relevance": 8,
    "scientific_credibility": 9,
    "educational_value": 7,
    "innovation_significance": 8,
    "public_interest": 6,
    "practical_patient_relevance": 8,
    "is_promotional": false,
    "is_low_quality": false,
    "is_us_centric": false,
    "clinical_risk_topic": false,
    "reasoning": "Brief explanation."
  }}
]


Articles to evaluate:
{json.dumps(articles_data, indent=2)}
"""
        try:
            response_text = self.run_llm(
                prompt=prompt,
                system_instruction=system_instruction,
                mime_type="application/json"
            )
            scores = json.loads(response_text)
            
            scored_map = {item["index"]: item for item in scores if "index" in item}
            for idx, art in enumerate(articles):
                score_info = scored_map.get(idx)
                if score_info:
                    art["category"] = score_info.get("category", "General Dentistry")
                    art["scores"] = {
                        "clinical_relevance": int(score_info.get("clinical_relevance", 5)),
                        "scientific_credibility": int(score_info.get("scientific_credibility", 5)),
                        "educational_value": int(score_info.get("educational_value", 5)),
                        "innovation_significance": int(score_info.get("innovation_significance", 5)),
                        "public_interest": int(score_info.get("public_interest", 5)),
                        "practical_patient_relevance": int(score_info.get("practical_patient_relevance", 5)),
                    }
                    art["is_promotional"] = bool(score_info.get("is_promotional", False))
                    art["is_low_quality"] = bool(score_info.get("is_low_quality", False))
                    art["is_us_centric"] = bool(score_info.get("is_us_centric", False))
                    art["is_inappropriate"] = False
                    art["clinical_risk_topic"] = bool(score_info.get("clinical_risk_topic", False))
                    art["scoring_reasoning"] = score_info.get("reasoning", "")
                else:
                    art.update(get_fallback_article_scores(art))
        except Exception as e:
            print(f"[EditorialAgent] Error scoring with Gemini: {e}. Using heuristic fallback.")
            return heuristic_score_and_classify(articles, self.search_console_snapshot)

        return add_strategic_evaluation(articles, search_console_snapshot=self.search_console_snapshot)

    def choose_best_candidate(self, top_3_articles, recent_posts=None, memory=None):
        """
        Presents the top 3 candidate articles and selects the absolute best, incorporating memory lessons
        and explicitly avoiding topics similar to recent publications.
        """
        if not top_3_articles:
            return None
        if len(top_3_articles) == 1:
            return top_3_articles[0]

        if not self.client:
            print("[EditorialAgent] Warning: Gemini client not available for final selection. Selecting highest scored candidate.")
            return top_3_articles[0]

        candidates_info = []
        for idx, art in enumerate(top_3_articles):
            candidates_info.append({
                "index": idx,
                "title": art.get("title"),
                "category": art.get("category"),
                "source": art.get("source"),
                "summary": art.get("summary"),
                "image": art.get("image"),
                "score": art.get("final_score"),
                "scoring_reasoning": art.get("scoring_reasoning"),
                "strategic_scores": art.get("strategic_scores"),
                "related_dentplant_pages": art.get("related_dentplant_pages"),
                "clinical_risk_topic": art.get("clinical_risk_topic"),
            })

        lessons_block = memory.get_lessons_prompt_block() if memory else ""
        
        history_block = ""
        if recent_posts:
            history_block = "**Recently Published Topics (DO NOT REPEAT):**\n" + "\n".join([f"- {t}" for t in recent_posts])

        system_instruction = (
            "You are an expert Dental Editorial Director selecting the single best candidate for publication. "
            "Evaluate clinical value, Dentplant strategic fit, topic diversity, and quality of visual assets."
        )

        prompt = f"""
We have narrowed down this week's news to the top 3 candidate articles. 
Select the absolute BEST candidate for publication on our premium practice blog, Dentplant.

{lessons_block}

{history_block}

Considerations:
- Clinical relevance, evidence strength, patient interest, and Dentplant strategic score.
- Legitimate risk or complication education is eligible. Exclude it only when it is sensationalist, misleading, unsupported, disproportionately alarmist, or otherwise low quality.
- **TOPIC DIVERSITY:** Do not select a candidate that is substantially similar to the recently published topics listed above.
- High-quality image availability (prefer clinical/authentic images over stock or none).
- Rationale of why this candidate is selected over the other two.

Candidates:
{json.dumps(candidates_info, indent=2)}

Output your decision as a JSON object:
{{
  "selected_index": <0, 1, or 2>,
  "rationale": "Detail here why this article was selected over the other two candidates, explicitly mentioning how it differs from recent history."
}}
"""
        try:
            response_text = self.run_llm(
                prompt=prompt,
                system_instruction=system_instruction,
                mime_type="application/json"
            )
            decision = json.loads(response_text)
            sel_idx = int(decision.get("selected_index", 0))
            if 0 <= sel_idx < len(top_3_articles):
                chosen = top_3_articles[sel_idx]
                chosen["selection_rationale"] = decision.get("rationale", "")
                print(f"[EditorialAgent] Selected candidate [{sel_idx}] ({chosen['title']})")
                return chosen
        except Exception as e:
            print(f"[EditorialAgent] Error selecting best candidate: {e}. Defaulting to first candidate.")
            
        return top_3_articles[0]
