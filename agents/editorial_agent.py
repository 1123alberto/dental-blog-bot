import re
import json
from agents.base import BaseAgent

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
        "scoring_reasoning": "Fallback score"
    }


def heuristic_score_and_classify(articles):
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
        art["scoring_reasoning"] = "Heuristically calculated"

    return articles


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
        pos_score = sum(art.get("scores", {}).values())
        img_score = score_image(art)
        art["image_score"] = img_score
        
        penalty = art.get("history_penalty", 0)
        if art.get("is_promotional"):
            penalty += 30
        if art.get("is_low_quality"):
            penalty += 25
            
        final_score = pos_score + img_score - penalty
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
    def __init__(self, client=None, model_name="gemini-3.5-flash"):
        super().__init__(client, model_name)

    def score_and_select(self, articles, recent_posts, memory=None):
        """
        Runs the full editorial evaluation process.
        """
        print("[EditorialAgent] Evaluating articles...")
        if not articles:
            print("[EditorialAgent] No articles provided for evaluation.")
            return None

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

        # 5. Choose the absolute best candidate using Gemini
        best_candidate = self.choose_best_candidate(top_3, memory)
        return best_candidate

    def score_and_classify(self, articles):
        """
        Calls Gemini to score and categorize articles. Fallback to heuristics if API is unavailable.
        """
        if not self.client:
            print("[EditorialAgent] Warning: Gemini client not initialized. Using heuristic fallback scoring.")
            return heuristic_score_and_classify(articles)

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
   - is_promotional: true if it is a promotional press release, corporate/financial announcement, or low-value product advertisement.
   - is_low_quality: true if it is sensationalist, has weak scientific evidence, or is low-value/celebrity news.

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
                    art["scoring_reasoning"] = score_info.get("reasoning", "")
                else:
                    art.update(get_fallback_article_scores(art))
        except Exception as e:
            print(f"[EditorialAgent] Error scoring with Gemini: {e}. Using heuristic fallback.")
            return heuristic_score_and_classify(articles)

        return articles

    def choose_best_candidate(self, top_3_articles, memory=None):
        """
        Presents the top 3 candidate articles and selects the absolute best, incorporating memory lessons.
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
                "scoring_reasoning": art.get("scoring_reasoning")
            })

        lessons_block = memory.get_lessons_prompt_block() if memory else ""

        system_instruction = (
            "You are an expert Dental Editorial Director selecting the single best candidate for publication. "
            "Evaluate clinical value, topic diversity, and quality of visual assets."
        )

        prompt = f"""
We have narrowed down this week's news to the top 3 candidate articles. 
Select the absolute BEST candidate for publication on our premium practice blog, Dentplant.

{lessons_block}

Considerations:
- Clinical relevance, evidence strength, patient interest.
- High-quality image availability (prefer clinical/authentic images over stock or none).
- Rationale of why this candidate is selected over the other two.

Candidates:
{json.dumps(candidates_info, indent=2)}

Output your decision as a JSON object:
{{
  "selected_index": <0, 1, or 2>,
  "rationale": "Detail here why this article was selected over the other two candidates."
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
