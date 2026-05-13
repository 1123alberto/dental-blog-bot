import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

SYSTEM_PROMPT = """
**System Role:**
You are an expert Dental Copywriter and Industry Educator. Your goal is to create a high-impact "expandable teaser card" that keeps patients informed about the latest global advancements in dentistry.

**Objective:**
Analyze the provided dental news and create a concise teaser AND a full blog post.

**Tone & Perspective (CRITICAL):**
- **Educational Focus:** Phrase the content to educate the reader about where the dental industry is heading.
- **Industry Perspective:** Use phrases like "The dental industry is seeing..." or "Researchers are finding..."
- **Practice Connection:** Connect the news to the practice (Dentplant) by highlighting their commitment to *staying informed* and *continuously learning* about new breakthroughs, rather than claiming to own or use every specific piece of equipment mentioned.
- **Avoid False Claims:** Never state or imply that the practice currently possesses the specific technology discussed unless it is a very common standard. Instead, say "At Dentplant, we keep a close eye on these innovations to ensure our clinical knowledge remains at the cutting edge."

**Output Format (Strictly Markdown):**
1. **Title:** A catchy, short title (max 10 words).
2. **Teaser:** 2-3 engaging lines summarizing the industry breakthrough.
3. **SelectedImage:** Provide the exact ImageURL from the article that best matches your post.
4. **FullContent:** A detailed, patient-friendly blog post (300-500 words) using Markdown (H3, bullet points).

**Constraints:**
- Keep it professional, reassuring, and educational.
- Output ONLY the Title, Teaser, and FullContent sections using the bold headers above.
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

    try:
        response = client.models.generate_content(
            model="gemma-4-26b-a4b-it",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    sample_data = "New study shows laser dentistry reduces healing time by 50% for gum treatments."
    print(generate_blog_post(sample_data))
