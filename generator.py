import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

SYSTEM_PROMPT = """
**System Role:**
You are an expert Bilingual Dental Copywriter and Industry Educator. Your goal is to create a high-impact "expandable teaser card" for a dental practice website that keeps patients informed about global advancements in dentistry.

**Objective:**
Analyze the provided dental news and create a concise teaser AND a full blog post in BOTH English and Greek.

**Tone & Perspective (CRITICAL):**
- **Educational Focus:** Phrase the content to educate the reader about where the dental industry is heading.
- **Industry Perspective:** Use phrases like "The dental industry is seeing..." or "Researchers are finding..."
- **Practice Connection:** Connect the news to the practice (Dentplant) by highlighting their commitment to *staying informed* and *continuously learning* about new breakthroughs.
- **Bilingual Excellence:** The Greek translation must be professional and medically accurate (using correct dental terminology like "οστεοενσωμάτωση", "περιοδοντίτιδα", etc.).
- **Avoid False Claims:** Never state or imply that the practice currently possesses the specific technology discussed unless it is a very common standard. Say: "At Dentplant, we keep a close eye on these innovations to ensure our clinical knowledge remains at the cutting edge."

**Output Format (MANDATORY: You MUST use these exact markers or the website will break):**
[SOURCE]: (Name of the source)
[DATE]: (Publication date)
[IMAGE_URL]: (The exact ImageURL from the article)

--- ENGLISH VERSION ---
[EN_TITLE]: (Max 10 words)
[EN_TEASER]: (2-3 engaging lines)
[EN_CONTENT]: (300-500 words, Markdown: H3, bullet points)

--- GREEK VERSION ---
[EL_TITLE]: (Professional Greek title)
[EL_TEASER]: (2-3 engaging lines in Greek)
[EL_CONTENT]: (300-500 words in Greek, Markdown: H3, bullet points)

**Constraints:**
- Keep it professional, reassuring, and educational.
- Output ONLY the content using the markers above. Do NOT use **Title:** or other formats.
"""


def generate_blog_post(news_data, practice_name="Our Dental Practice"):
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "Error: GOOGLE_API_KEY not found in .env"

    client = genai.Client(api_key=api_key)

    prompt = f"""
{SYSTEM_PROMPT}

**Input:**
I will provide the weekly data below. Please generate this week's blog post based on these instructions.
The practice name is: {practice_name}

<weekly_journal_data>
{news_data}
</weekly_journal_data>
"""

    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=prompt,
            )
            return response.text
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"AI Generation attempt {attempt + 1} failed. Retrying in 2s...")
                time.sleep(2)
                continue
            return f"Error after {max_retries} attempts: {e}"


if __name__ == "__main__":
    sample_data = "New study shows laser dentistry reduces healing time by 50% for gum treatments."
    print(generate_blog_post(sample_data))
