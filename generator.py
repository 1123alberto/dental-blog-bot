import os
import re
import json

from dotenv import load_dotenv
from google import genai

load_dotenv()

SYSTEM_PROMPT = """You are an expert Dental Editorial Director, Clinical Content Strategist, and Bilingual Medical Copywriter for a modern dental practice website.

Your role is NOT simply to rewrite articles.

Your responsibilities are to:

* Curate the most valuable dental industry developments
* Filter out repetitive or low-value stories
* Detect duplicate or syndicated content
* Translate complex research into patient-friendly education
* Create authoritative bilingual educational content
* Maintain editorial quality, topic diversity, and medical credibility

OBJECTIVE:
Analyze all provided dental news and research sources and select ONLY the single best article for publication.

EDITORIAL SELECTION PROCESS:

Before generating content:

1. Compare all fetched articles.

2. Detect syndicated or near-duplicate stories.

3. If multiple articles discuss the same study, product, event, or discovery:

   * Select ONLY the most authoritative version
   * Prefer original reporting, peer-reviewed studies, university research, or primary sources
   * Ignore rewritten or syndicated copies

4. Rank candidate articles using:

   * Clinical relevance
   * Scientific credibility
   * Educational value
   * Innovation significance
   * Public interest
   * Practical patient relevance

5. Avoid:

   * Promotional press releases
   * Financial or corporate business-only stories
   * Duplicate themes
   * Sensationalism
   * Weak scientific evidence
   * Celebrity-focused content
   * Low-value product announcements

6. Prioritize topics related to:

   * Implantology
   * Periodontology
   * Digital dentistry
   * Preventive dentistry
   * Cosmetic dentistry
   * Oral-systemic health
   * Minimally invasive dentistry
   * AI with genuine clinical relevance
   * Diagnostic innovation
   * Long-term oral health

7. Maintain topic diversity:

   * Avoid repeating similar themes in consecutive articles
   * Rotate categories over time
   * Avoid over-publishing AI, implant, or cosmetic stories consecutively

SOURCE PRIORITY:

Tier 1 (highest authority):

* Peer-reviewed journals
* University research
* Clinical studies
* Scientific publications

Tier 2:

* Major dental education publications
* Professional organizations
* Established medical publishers

Tier 3:

* Industry news websites
* Business and trade publications

When duplicate stories exist:

* Prefer Tier 1 sources first.

WRITING APPROACH:

Do NOT merely summarize the article.

Instead:

* Interpret the findings
* Explain their significance
* Connect them to modern patient care
* Present the topic as an evolving development in dentistry

The article should feel like an expert editorial analysis written for educated patients — NOT a rewritten press release.

TONE & STYLE:

The writing must be:

* Educational
* Professional
* Evidence-informed
* Reassuring
* Patient-friendly
* Medically credible
* Editorial in tone
* Natural and human-like

Avoid generic AI phrasing such as:

* “Researchers are finding…”
* “Modern dentistry is uncovering…”
* “Recent studies suggest…”

Use more natural, authoritative editorial language.

Avoid exaggerated claims.
Avoid sensationalism.
Do not imply experimental technologies are standard clinical care.

Clearly distinguish between:

* emerging research,
* early clinical adoption,
* and established treatment methods.

ARTICLE STRUCTURE:

Structure the article using:

* A compelling opening hook
* Short readable sections
* H3 Markdown subheadings
* Occasional bullet points where useful
* A strong practical takeaway

Avoid large uninterrupted blocks of text.

The article MUST explain:

* What happened
* Why it matters
* Potential future impact
* Practical patient relevance
* Important limitations or uncertainty

HUMANIZATION & PATIENT RELEVANCE:

Include practical patient context where appropriate, such as:

* Silent infections
* Hidden inflammation
* Painless dental problems
* Preventive care
* Early diagnosis
* Routine radiographs
* Long-term oral health
* Links between oral and systemic health

Use 1–3 precise dental or medical terms naturally within the article to improve authority and specificity, while remaining understandable to patients.

EXAMPLES:

* Apical periodontitis
* Osseointegration
* Periodontal inflammation
* Peri-implantitis
* Biofilm
* Endodontic infection
* Occlusal wear
* Salivary diagnostics

PRACTICE CONNECTION:

Mention Dentplant naturally as a practice committed to:

* Continuing education
* Scientific awareness
* Staying informed about advances in modern dentistry
* Evidence-based care

Never falsely claim the practice offers a specific technology unless it is clearly established and commonly available.

BILINGUAL REQUIREMENTS:

* English and Greek versions must communicate the SAME meaning and nuance.
* The Greek translation must be medically accurate and professionally written.
* Use proper dental terminology in Greek where appropriate.

SEO GUIDELINES:

Naturally incorporate relevant dental terminology and search-friendly phrases without keyword stuffing.

Examples:

* Dental implants
* Gum disease
* Oral health
* Preventive dentistry
* Digital dentistry
* Cosmetic dentistry
* Periodontal health
* Root canal treatment

OUTPUT FORMAT (MANDATORY):
You MUST use these exact markers.

[SOURCE]: [DATE]:

[IMAGE_URL]:

--- ENGLISH VERSION ---
[EN_TITLE]:
[EN_TEASER]:
[EN_CONTENT]:

--- GREEK VERSION ---
[EL_TITLE]:
[EL_TEASER]:
[EL_CONTENT]:

TITLE RULES:

* Maximum 12 words
* Professional and medically credible
* Avoid clickbait
* Clearly communicate the topic

TEASER RULES:

* 2–3 concise engaging lines
* Educational and curiosity-driven
* Avoid hype

CONTENT RULES:

* 300–500 words per language
* Use Markdown formatting
* Use H3 subheadings
* Include occasional bullet points when helpful
* Maintain readability and flow

FINAL CONSTRAINTS:

* Output ONLY the requested format markers
* No additional commentary
* No explanations outside the format
* No fabricated clinical claims
* No exaggerated medical promises

If an article is repetitive, low-value, weakly sourced, overly promotional, or too similar to recently covered topics:
DO NOT generate content for it.
Select another article instead.

IMAGE SELECTION RULES:

The featured image is critically important and must feel authentic, professional, medically credible, and visually relevant to the article topic.

IMAGE PRIORITY ORDER:

1. Use the ORIGINAL article featured image whenever available.

2. Prefer:

   * Clinical photographs
   * Research visuals
   * Real dental equipment
   * Real clinicians or laboratories
   * Scientific imagery
   * Authentic healthcare environments


3. Avoid (unless absolutely necessary as a worst-case fallback to avoid publishing without an image):
   * AI-generated artwork (unless relative to the story and used as a last resort)

4. Avoid:
   * Cartoon-style illustrations
   * Unrealistic smiling stock models
   * Generic tooth icons
   * Overly staged corporate stock photos
   * Low-resolution images
   * Watermarked images
   * Duplicate or recently used images

5. NEVER reuse the same image in consecutive posts unless the article is part of the same ongoing story.

6. If multiple image options exist:

   * Prefer the image most directly connected to the study or clinical topic
   * Prefer images from the original publisher
   * Prefer landscape-oriented professional images
   * Prefer medically realistic imagery over marketing-style visuals

7. If the article image appears AI-generated, synthetic, overly polished, or unrelated to the topic:

   * Try to select another higher-quality authentic image first.
   * If no other image exists, you may use it as a fallback if it is relative to the story, rather than leaving IMAGE_URL blank.

8. Before selecting an image:

   * Compare it against recently used images
   * Avoid visual repetition
   * Avoid using identical stock imagery across multiple posts

9. The image must visually match the article topic.

Examples:

* Oral-systemic health article → clinical or medical imagery
* Implantology article → implants, CBCT scans, surgical planning
* AI dentistry article → realistic digital workflow or diagnostics
* Periodontal article → gums, inflammation, preventive care
* Research article → laboratory, microscopy, university, or clinician imagery

9. Do not select images containing:

   * exaggerated cosmetic smiles,
   * unrealistic anatomy,
   * visibly AI-generated faces or teeth (unless used as a worst-case last-resort fallback),
   * distorted hands or instruments,
   * fantasy-style rendering,
   * or heavily manipulated visuals.

10. If no suitable authentic image exists:

* As a worst-case scenario, to avoid publishing without an image, you may use an AI-generated or stock image from the feeds that is relative to the story, instead of leaving it blank.

The quality of the featured image is important, but to ensure all posts look professional and complete, we must avoid publishing articles without images. If no premium authentic image is available, choose a relative-to-the-story AI-generated or stock image from the source feeds as a last-resort fallback instead of returning an empty IMAGE_URL.
"""


def generate_content_with_fallback(client, prompt, config=None, initial_model="gemini-2.5-flash"):
    models = [initial_model, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]
    unique_models = []
    for m in models:
        if m not in unique_models:
            unique_models.append(m)
            
    last_error = None
    import time
    for model_name in unique_models:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config
                )
                return response
            except Exception as e:
                last_error = e
                print(f"Failed to generate content with {model_name} (attempt {attempt+1}): {e}")
                time.sleep(1)
    raise last_error


def deduplicate_articles(articles):
    """
    Step 3: Deduplication engine
    Uses Jaccard similarity on lowercased and stripped words in the titles.
    If Jaccard similarity is > 0.35, the articles are considered duplicates.
    Keeps only the best article from each duplicate group.
    """
    def clean_title(title):
        if not title:
            return set()
        title = title.lower()
        # Remove common punctuation
        title = re.sub(r'[^\w\s]', '', title)
        words = set(title.split())
        # Filter stop words
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
            # Check similarity with members of the group
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

    # For each group, choose the best representative
    representatives = []
    for group in unique_groups:
        if len(group) == 1:
            representatives.append(group[0])
            continue
        
        # Sort members by criteria:
        # 1. Source Tier (Tier 1 > Tier 2 > Tier 3)
        # 2. Presence of image
        # 3. Content/summary length
        def get_source_tier(source_name):
            source_name = source_name.lower()
            # Tier 1: Peer-reviewed, university, clinical
            t1_keywords = ["journal", "university", "clinical", "wiley", "nature", "science", "lancet", "periodontology"]
            # Tier 2: Major education, professional orgs
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


def score_and_classify_articles(client, articles):
    """
    Steps 4 & 5: Article scorer & Category classifier
    Sends the articles to Gemini to score them on quality/relevance/credibility 
    and classify them into one of the key dental categories.
    """
    if not articles:
        return []

    # If API key is missing or client is mock/None, use fallback heuristic scorer
    if not client:
        print("Warning: Gemini client not available for scoring. Using heuristic backup scoring.")
        return heuristic_score_and_classify(articles)

    # Format the articles for the prompt
    articles_data = []
    for idx, art in enumerate(articles):
        articles_data.append({
            "index": idx,
            "title": art.get("title"),
            "source": art.get("source"),
            "summary": art.get("summary")[:300] if art.get("summary") else ""
        })

    prompt = f"""
You are an expert Dental Editorial Director. Analyze these {len(articles)} dental news articles.
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

Return the response as a JSON array of objects, each representing the scoring for the article with the corresponding index.
Example output format:
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
    "reasoning": "Brief explanation of the scores."
  }}
]

Articles:
{json.dumps(articles_data, indent=2)}
"""
    try:
        response = generate_content_with_fallback(
            client=client,
            prompt=prompt,
            config={"response_mime_type": "application/json"},
            initial_model="gemini-2.5-flash"
        )
        scores = json.loads(response.text)
        
        # Map scores back to the articles
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
        print(f"Error scoring articles with Gemini: {e}. Using heuristic scoring fallback.")
        for art in articles:
            art.update(get_fallback_article_scores(art))

    return articles


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
    Fallback scorer in case of Gemini failures or missing API keys.
    Uses simple rule-based heuristics.
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
    Step 6: Image validator/scorer
    Scores the image URL of an article based on selection rules:
    - High-quality/Clinical photo = 10
    - Stock/AI-generated last-resort fallback = 5
    - Generic/Missing/Watermarked = 0
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
    Step 7: Recent-history filter
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
    Step 8: TOP 3 candidates only
    Sorts articles by final score and returns top 3.
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


def choose_best_candidate(client, top_3_articles):
    """
    Step 9: Gemini chooses BEST candidate
    Present the top 3 candidates to Gemini and let it choose the absolute best candidate.
    """
    if not top_3_articles:
        return None

    if len(top_3_articles) == 1:
        return top_3_articles[0]

    if not client:
        print("Warning: Gemini client not available to select best candidate. Choosing highest scoring candidate.")
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

    prompt = f"""
You are an expert Dental Editorial Director. We have narrowed down this week's news to the top 3 candidate articles.
Select the absolute BEST candidate for publication on our premium practice blog, Dentplant.

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
        response = generate_content_with_fallback(
            client=client,
            prompt=prompt,
            config={"response_mime_type": "application/json"},
            initial_model="gemini-2.5-flash"
        )
        decision = json.loads(response.text)
        sel_idx = int(decision.get("selected_index", 0))
        if 0 <= sel_idx < len(top_3_articles):
            chosen = top_3_articles[sel_idx]
            chosen["selection_rationale"] = decision.get("rationale", "")
            print(f"Gemini selected candidate [{sel_idx}] as the best candidate. Rationale: {chosen['selection_rationale']}")
            return chosen
    except Exception as e:
        print(f"Error during Gemini selection: {e}. Choosing highest scoring candidate by default.")
        
    return top_3_articles[0]


def write_article(client, best_candidate, practice_name="Dentplant"):
    """
    Step 10: Gemini writes article
    Generates the final bilingual blog post in the required format.
    """
    if not best_candidate:
        return "Error: No candidate selected"

    if not client:
        return "Error: Gemini client not initialized"

    article_details = f"""
Title: {best_candidate.get('title')}
Source: {best_candidate.get('source')}
Date: {best_candidate.get('date')}
ImageURL: {best_candidate.get('image')}
Extracted Text:
{best_candidate.get('full_text')}
"""

    prompt = f"""
{SYSTEM_PROMPT}

**Selected Article to Write About:**
{article_details}

**Practice Name:** {practice_name}

Generate the blog post now following all guidelines and the output format exactly.
"""
    try:
        response = generate_content_with_fallback(
            client=client,
            prompt=prompt,
            initial_model="gemini-2.5-flash"
        )
        return response.text
    except Exception as e:
        return f"Error writing blog post: {e}"


def generate_blog_post(news_data, practice_name="Our Dental Practice", recent_posts=None):
    # Parse string to list if necessary
    if isinstance(news_data, str):
        articles = []
        parts = news_data.split("--- Article")
        for part in parts:
            if not part.strip():
                continue
            lines = part.strip().split("\n")
            art = {"full_text": "", "summary": "", "image": None}
            for line in lines:
                if line.startswith("Title:"):
                    art["title"] = line[len("Title:"):].strip()
                elif line.startswith("Source:"):
                    art["source"] = line[len("Source:"):].strip()
                elif line.startswith("Date:"):
                    art["date"] = line[len("Date:"):].strip()
                elif line.startswith("Summary:"):
                    art["summary"] = line[len("Summary:"):].strip()
                    art["full_text"] = art["summary"]
                elif line.startswith("ImageURL:"):
                    art["image"] = line[len("ImageURL:"):].strip()
            if "title" in art:
                articles.append(art)
    else:
        articles = news_data

    if not articles:
        return "Error: No articles to process"

    api_key = os.getenv("GOOGLE_API_KEY")
    client = None
    if api_key:
        try:
            client = genai.Client(api_key=api_key)
        except Exception as e:
            print(f"Warning: Could not initialize Gemini Client: {e}")

    # Deduplicate articles
    unique_articles = deduplicate_articles(articles)
    if not unique_articles:
        return "Error: All articles deduplicated"

    # Score and classify articles
    scored_articles = score_and_classify_articles(client, unique_articles)

    # Recent-history filter
    filtered_articles = apply_history_filter(scored_articles, recent_posts)

    # TOP 3 candidates only (Includes Image validation/scoring)
    top_3 = get_top_3_candidates(filtered_articles)
    if not top_3:
        return "Error: No top candidates selected"

    # Gemini chooses BEST candidate
    best_candidate = choose_best_candidate(client, top_3)
    if not best_candidate:
        return "Error: No best candidate selected"

    # Gemini writes article
    if not client:
        return f"Error: GOOGLE_API_KEY not found in .env or invalid. Choose BEST candidate heuristically: {best_candidate.get('title')}"

    return write_article(client, best_candidate, practice_name)


if __name__ == "__main__":
    sample_data = "New study shows laser dentistry reduces healing time by 50% for gum treatments."
    print(generate_blog_post(sample_data))

