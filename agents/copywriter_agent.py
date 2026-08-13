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

    def write_post(self, best_candidate, practice_name="Dentplant", memory=None, content_brief=None):
        """
        Drafts the bilingual post using a 2-step process (English then Greek)
        to prevent language bleeding and ensure the highest editorial standards.
        """
        print("[CopywriterAgent] Commencing sequential copywriting...")
        if not best_candidate:
            return "Error: No candidate selected"

        # Step 1: Draft English version
        en_post = self._draft_english(best_candidate, practice_name, memory, content_brief)

        # Step 2: Translate and rewrite into professional Greek
        el_post = self._draft_greek(best_candidate, en_post, practice_name, memory, content_brief)

        # Step 3: Combine with format markers
        formatted_post = self._assemble_post(best_candidate, en_post, el_post, content_brief)
        return formatted_post

    def refine_post(self, draft, feedback_list, best_candidate, practice_name="Dentplant", content_brief=None):
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

{self._brief_prompt_block(content_brief)}

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
            return self._append_link_plan(refined_text.strip(), content_brief)
        except Exception as e:
            print(f"[CopywriterAgent] Error during refinement: {e}")
            return draft

    def _draft_english(self, candidate, practice_name, memory=None, content_brief=None):
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

{self._brief_prompt_block(content_brief)}

Draft the **ENGLISH** version of the blog post.
Your response MUST contain exactly:
1. Title: Compelling, professional, max 12 words. Do NOT use markdown formatting (like asterisks) in the title.
2. Teaser: 2-3 engaging, educational lines.
3. Content: 300-500 words. Use H3 markdown headers for sections. Use 1-3 precise clinical terms naturally. Mention {practice_name} commitement to evidence-based care.
4. When a ContentBrief is provided, it is mandatory: follow its angle and primary patient intent; use only its source-supported claims for research-specific statements; preserve its evidence maturity and uncertainty; obey duplication/risk/practice constraints. Do not add statistics unless present in the supported claims.

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

    def _draft_greek(self, candidate, en_post, practice_name, memory=None, content_brief=None):
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

{self._brief_prompt_block(content_brief)}

Draft the **GREEK** version of the blog post. It must match the meaning and structure of the English draft, but be written in natural, fluent, and professional Greek.
Your response MUST contain exactly:
1. Title: Greek translation of the title. Do NOT use markdown formatting in the title. Max 12 words.
2. Teaser: Greek translation of the teaser.
3. Content: 300-500 words in Greek. Use H3 markdown headers. Include correct Greek medical terminology (e.g., peri-implantitis -> περιεμφυτευματίτιδα, osseointegration -> οστεοενσωμάτωση). Mention {practice_name} commitement to evidence-based care in Greek.
4. Preserve exactly the English draft's evidence maturity, uncertainty, source-supported claims, and ContentBrief constraints. Do not introduce claims or statistics absent from the English version or ContentBrief.

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

    def _brief_prompt_block(self, content_brief):
        if not content_brief:
            return ""
        claims = content_brief.get("claims", [])
        claim_lines = "\n".join(f"- {claim.get('claim')} (confidence: {claim.get('confidence')})" for claim in claims) or "- No research-specific claim supplied."
        links = "\n".join(
            f"- {link.get('target_path')}: EN '{link.get('anchor_en')}', EL '{link.get('anchor_el')}'"
            for link in content_brief.get("recommended_internal_links", [])
        ) or "- No internal-link directives planned."
        return f"""
**MANDATORY CONTENT BRIEF (do not reinterpret or expand it):**
Article angle: {content_brief.get('article_angle')}
Primary patient intent: {content_brief.get('primary_patient_intent')}
Secondary intents: {', '.join(content_brief.get('secondary_patient_intents', [])) or 'None'}
Dentplant cluster: {content_brief.get('primary_cluster')}
Evidence maturity: {content_brief.get('evidence_maturity')}
Supported claims only:
{claim_lines}
Duplication avoidance:
{chr(10).join('- ' + item for item in content_brief.get('duplication_avoidance', []))}
Clinical-risk notes:
{chr(10).join('- ' + item for item in content_brief.get('clinical_risk_notes', [])) or '- None'}
Editorial constraints:
{chr(10).join('- ' + item for item in content_brief.get('editorial_constraints', []))}
Planned internal-link concepts (do not render links or invent targets; final directives are added separately):
{links}
"""

    def _link_plan(self, content_brief):
        if not content_brief or not content_brief.get("recommended_internal_links"):
            return ""
        lines = ["--- INTERNAL LINK PLAN ---"]
        for index, link in enumerate(content_brief["recommended_internal_links"], 1):
            lines.extend([
                f"[LINK_{index}_TARGET]: {link.get('target_path', '')}",
                f"[LINK_{index}_ANCHOR_EN]: {link.get('anchor_en', '')}",
                f"[LINK_{index}_ANCHOR_EL]: {link.get('anchor_el', '')}",
                f"[LINK_{index}_CONTEXT_EN]: {link.get('reason', '')}",
                f"[LINK_{index}_CONTEXT_EL]: {link.get('reason', '')}",
            ])
        return "\n".join(lines)

    def _append_link_plan(self, draft, content_brief):
        draft = re.split(r"\n--- INTERNAL LINK PLAN ---", draft, maxsplit=1)[0].rstrip()
        plan = self._link_plan(content_brief)
        return f"{draft}\n\n{plan}" if plan else draft

    def _assemble_post(self, candidate, en_post, el_post, content_brief=None):
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
        return self._append_link_plan(assembled, content_brief)
