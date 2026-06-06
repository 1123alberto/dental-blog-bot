import os
import re
import json

from dotenv import load_dotenv
from google import genai

from agents import AgentMemory, ScraperAgent, EditorialAgent, CopywriterAgent, QAAgent, log_group_start, log_group_end

load_dotenv()


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


from agents.editorial_agent import (
    deduplicate_articles,
    heuristic_score_and_classify,
    apply_history_filter,
    get_top_3_candidates,
    get_fallback_article_scores,
    score_image
)

def score_and_classify_articles(client, articles):
    agent = EditorialAgent(client=client)
    return agent.score_and_classify(articles)

def choose_best_candidate(client, top_3_articles):
    agent = EditorialAgent(client=client)
    return agent.choose_best_candidate(top_3_articles)

def write_article(client, best_candidate, practice_name="Dentplant"):
    agent = CopywriterAgent(client=client)
    return agent.write_post(best_candidate, practice_name)


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

    # Set model name from environment or default to gemini-3.5-flash
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

    # Initialize Agents & Memory
    memory = AgentMemory()
    editorial_agent = EditorialAgent(client=client, model_name=model_name)
    copywriter_agent = CopywriterAgent(client=client, model_name=model_name)
    qa_agent = QAAgent(client=client, model_name=model_name)

    # 1. Select the best candidate article using the Editorial Agent
    log_group_start("[2] Editorial Evaluation & Article Selection")
    best_candidate = editorial_agent.score_and_select(articles, recent_posts or [], memory)
    log_group_end()
    
    if not best_candidate:
        # Fallback to the first candidate if scoring failed to produce a result
        if articles:
            best_candidate = articles[0]
        else:
            return "Error: No candidate selected"

    # 2. Check if we have API key for content generation
    if not client:
        # If API key is missing or client is mock/None, choose heuristically and return fallback warning
        return f"Error: GOOGLE_API_KEY not found in .env or invalid. Choose BEST candidate heuristically: {best_candidate.get('title')}"

    # 3. Draft the initial article using the Copywriter Agent
    log_group_start("[3] Copywriter Drafting (Bilingual)")
    blog_markdown = copywriter_agent.write_post(best_candidate, practice_name, memory)
    log_group_end()

    # 4. QA Validation Feedback Loop
    log_group_start("[4] QA Validation Feedback Loop")
    max_qa_attempts = 3
    for attempt in range(max_qa_attempts):
        print(f"[Pipeline] Running QA Agent validation (Attempt {attempt+1}/{max_qa_attempts})...")
        is_valid, errors = qa_agent.validate_post(blog_markdown, practice_name)

        if is_valid:
            print("[Pipeline] QA Validation SUCCESS!")
            break
        else:
            print(f"[Pipeline] QA Validation FAILED with errors:")
            for err in errors:
                print(f"  - {err}")
            
            # Save feedback to Agent Memory to learn from it
            for err in errors:
                # Add learning memory
                memory.add_lesson(
                    category="copywriting",
                    error_description=err,
                    correction_rule=f"Do not repeat error: {err}. Adhere strictly to the guidelines."
                )

            if attempt < max_qa_attempts - 1:
                # Run Copywriter refinement
                blog_markdown = copywriter_agent.refine_post(blog_markdown, errors, best_candidate, practice_name)
            else:
                print("[Pipeline] Max QA attempts reached. Proceeding with best available draft.")
    log_group_end()

    return blog_markdown


if __name__ == "__main__":
    sample_data = "New study shows laser dentistry reduces healing time by 50% for gum treatments."
    print(generate_blog_post(sample_data))

