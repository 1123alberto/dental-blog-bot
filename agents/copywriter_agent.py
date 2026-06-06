import re
from agents.base import BaseAgent
from agents.prompts import COPYWRITER_SYSTEM_PROMPT

class CopywriterAgent(BaseAgent):
    """
    CopywriterAgent handles sequential bilingual copywriting (English, then Greek)
    and executes targeted revisions when requested by the Quality Assurance Agent.
    """
    def __init__(self, client=None, model_name="gemini-3.5-flash"):
        super().__init__(client, model_name)

    def write_post(self, best_candidate, practice_name="Dentplant", memory=None):
        """
        Drafts the bilingual post using a 2-step process (English then Greek)
        to prevent language bleeding and ensure the highest editorial standards.
        """
        print("[CopywriterAgent] Commencing sequential copywriting...")
        if not best_candidate:
            return "Error: No candidate selected"

        # Step 1: Draft English version
        en_post = self._draft_english(best_candidate, practice_name, memory)

        # Step 2: Translate and rewrite into professional Greek
        el_post = self._draft_greek(best_candidate, en_post, practice_name, memory)

        # Step 3: Combine with format markers
        formatted_post = self._assemble_post(best_candidate, en_post, el_post)
        return formatted_post

    def refine_post(self, draft, feedback_list, best_candidate, practice_name="Dentplant"):
        """
        Performs targeted refinement of the draft based on QA feedback.
        """
        print(f"[CopywriterAgent] Refining draft based on {len(feedback_list)} feedback points...")
        feedback_str = "\n".join([f"- {fb}" for fb in feedback_list])

        prompt = f"""
You are the Bilingual Medical Copywriter. Your previous draft failed the Quality Assurance check.
You must correct the issues listed below while keeping the rest of the high-quality text.

**Selected Article to Write About:**
Title: {best_candidate.get('title')}
Source: {best_candidate.get('source')}
Date: {best_candidate.get('date')}
ImageURL: {best_candidate.get('image')}

**Practice Name:** {practice_name}

**QA Feedback / Errors to Fix:**
{feedback_str}

**Previous Draft:**
\"\"\"
{draft}
\"\"\"

Please rewrite the draft, addressing every single point in the QA Feedback.
Ensure your response follows the exact format markers:

[SOURCE]: [source name]
[DATE]: [date]
[IMAGE_URL]: [image url]

--- ENGLISH VERSION ---
[EN_TITLE]: [title]
[EN_TEASER]: [teaser]
[EN_CONTENT]: [content]

--- GREEK VERSION ---
[EL_TITLE]: [title]
[EL_TEASER]: [teaser]
[EL_CONTENT]: [content]
"""
        try:
            refined_text = self.run_llm(
                prompt=prompt,
                system_instruction="You are a professional Medical Copywriter. Correct the provided draft based on the QA report."
            )
            return refined_text.strip()
        except Exception as e:
            print(f"[CopywriterAgent] Error during refinement: {e}")
            return draft

    def _draft_english(self, candidate, practice_name, memory=None):
        """Drafts the English version of the blog post."""
        lessons_block = memory.get_lessons_prompt_block() if memory else ""

        system_instruction = (
            "You are an expert Dental Editorial Director and Clinical Content Writer. "
            "Draft a patient-focused, educational blog post in English based on clinical developments."
        )

        prompt = f"""
{COPYWRITER_SYSTEM_PROMPT}

{lessons_block}

**Selected Article to Analyze:**
Title: {candidate.get('title')}
Source: {candidate.get('source')}
Date: {candidate.get('date')}
Extracted Text:
{candidate.get('full_text')}

**Practice Name:** {practice_name}

Draft the **ENGLISH** version of the blog post.
Your response MUST contain exactly:
1. Title: Compelling, professional, max 12 words. Do NOT use markdown formatting (like asterisks) in the title.
2. Teaser: 2-3 engaging, educational lines.
3. Content: 300-500 words. Use H3 markdown headers for sections. Use 1-3 precise clinical terms naturally. Mention {practice_name} commitement to evidence-based care.

Format your output exactly as:
TITLE: [English Title]
TEASER: [English Teaser]
CONTENT:
[English Content]
"""
        try:
            en_draft = self.run_llm(
                prompt=prompt,
                system_instruction=system_instruction
            )
            return en_draft.strip()
        except Exception as e:
            print(f"[CopywriterAgent] Error drafting English version: {e}")
            # Minimal fallback structure
            return f"TITLE: {candidate.get('title')}\nTEASER: Latest dental insights.\nCONTENT:\n{candidate.get('summary')}"

    def _draft_greek(self, candidate, en_post, practice_name, memory=None):
        """Translates/rewrites the post into medical Greek."""
        lessons_block = memory.get_lessons_prompt_block() if memory else ""

        system_instruction = (
            "You are an expert Bilingual Medical Copywriter. Translate and adapt English dental "
            "clinical posts into professional, patient-friendly Greek medical text."
        )

        prompt = f"""
{COPYWRITER_SYSTEM_PROMPT}

{lessons_block}

**Original Article:**
Title: {candidate.get('title')}
Source: {candidate.get('source')}
Date: {candidate.get('date')}

**English Draft to Translate/Adapt:**
\"\"\"
{en_post}
\"\"\"

**Practice Name:** {practice_name}

Draft the **GREEK** version of the blog post. It must match the meaning and structure of the English draft, but be written in natural, fluent, and professional Greek.
Your response MUST contain exactly:
1. Title: Greek translation of the title. Do NOT use markdown formatting in the title. Max 12 words.
2. Teaser: Greek translation of the teaser.
3. Content: 300-500 words in Greek. Use H3 markdown headers. Include correct Greek medical terminology (e.g., peri-implantitis -> περιεμφυτευματίτιδα, osseointegration -> οστεοενσωμάτωση). Mention {practice_name} commitement to evidence-based care in Greek.

Format your output exactly as:
TITLE: [Greek Title]
TEASER: [Greek Teaser]
CONTENT:
[Greek Content]
"""
        try:
            el_draft = self.run_llm(
                prompt=prompt,
                system_instruction=system_instruction
            )
            return el_draft.strip()
        except Exception as e:
            print(f"[CopywriterAgent] Error drafting Greek version: {e}")
            return f"TITLE: {candidate.get('title')} (Greek)\nTEASER: Updates in Greek.\nCONTENT:\n{candidate.get('summary')}"

    def _assemble_post(self, candidate, en_post, el_post):
        """Assembles English and Greek posts into final format with markers."""
        # Helper to extract parts
        def parse_part(text):
            title_match = re.search(r"TITLE:\s*(.*?)(?=\nTEASER:|$)", text, re.DOTALL | re.IGNORECASE)
            teaser_match = re.search(r"TEASER:\s*(.*?)(?=\nCONTENT:|$)", text, re.DOTALL | re.IGNORECASE)
            content_match = re.search(r"CONTENT:\s*(.*)", text, re.DOTALL | re.IGNORECASE)

            title = title_match.group(1).strip() if title_match else ""
            teaser = teaser_match.group(1).strip() if teaser_match else ""
            content = content_match.group(1).strip() if content_match else ""
            return title, teaser, content

        en_title, en_teaser, en_content = parse_part(en_post)
        el_title, el_teaser, el_content = parse_part(el_post)

        # Build combined output
        assembled = f"""[SOURCE]: {candidate.get('source', 'Dental Journal')}
[DATE]: {candidate.get('date', 'Recently')}
[IMAGE_URL]: {candidate.get('image', '')}

--- ENGLISH VERSION ---
[EN_TITLE]: {en_title}
[EN_TEASER]: {en_teaser}
[EN_CONTENT]:
{en_content}

--- GREEK VERSION ---
[EL_TITLE]: {el_title}
[EL_TEASER]: {el_teaser}
[EL_CONTENT]:
{el_content}"""
        return assembled
