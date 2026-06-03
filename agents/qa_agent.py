import re
import json
from agents.base import BaseAgent

class QAAgent(BaseAgent):
    """
    QAAgent performs programmatic and LLM-based verification on the generated article
    to ensure formatting, length, and bilingual quality standards are met.
    """
    def __init__(self, client=None, model_name="gemini-3.5-flash"):
        super().__init__(client, model_name)

    def validate_post(self, markdown_content, practice_name="Dentplant"):
        """
        Runs programmatic checks and returns a tuple: (is_valid, list_of_errors_or_feedback).
        """
        errors = []

        # 1. Check for mandatory markers
        required_markers = [
            r"\[SOURCE\]:", r"\[DATE\]:", r"\[IMAGE_URL\]:",
            r"\[EN_TITLE\]:", r"\[EN_TEASER\]:", r"\[EN_CONTENT\]:",
            r"\[EL_TITLE\]:", r"\[EL_TEASER\]:", r"\[EL_CONTENT\]:"
        ]
        
        for marker in required_markers:
            if not re.search(marker, markdown_content, re.IGNORECASE):
                clean_marker = marker.replace('\\', '')
                errors.append(f"Missing required marker: {clean_marker}")

        if errors:
            # If markers are missing, we cannot parse sections for further analysis
            return False, errors

        # 2. Extract sections for analysis
        def get_field(marker, next_marker=None):
            pattern = rf"{marker}\s*(.*?)(?=\n{next_marker}|\n\[|$)" if next_marker else rf"{marker}\s*(.*)"
            match = re.search(pattern, markdown_content, re.DOTALL | re.IGNORECASE)
            return match.group(1).strip() if match else ""

        en_title = get_field(r"\[EN_TITLE\]:", r"\[EN_TEASER\]:")
        en_teaser = get_field(r"\[EN_TEASER\]:", r"\[EN_CONTENT\]:")
        en_content = get_field(r"\[EN_CONTENT\]:", r"--- GREEK VERSION ---|\[EL_TITLE\]:")
        
        el_title = get_field(r"\[EL_TITLE\]:", r"\[EL_TEASER\]:")
        el_teaser = get_field(r"\[EL_TEASER\]:", r"\[EL_CONTENT\]:")
        el_content = get_field(r"\[EL_CONTENT\]:")

        # 3. Title validation (no asterisks, length check)
        for lang, title in [("English", en_title), ("Greek", el_title)]:
            if "**" in title or "*" in title:
                errors.append(f"{lang} title must not contain markdown bold/italic asterisks ('*').")
            words = title.split()
            if len(words) > 12:
                errors.append(f"{lang} title exceeds 12 words limit (current: {len(words)} words).")
            if not title:
                errors.append(f"{lang} title is empty.")

        # 4. Teaser validation
        for lang, teaser in [("English", en_teaser), ("Greek", el_teaser)]:
            if not teaser:
                errors.append(f"{lang} teaser is empty.")

        # 5. Practice name presence
        for lang, content in [("English", en_content), ("Greek", el_content)]:
            if practice_name.lower() not in content.lower():
                errors.append(f"{lang} content does not mention the practice name '{practice_name}'.")

        # 6. Word count validation (300-500 words)
        def clean_word_count(text):
            # Strip headers and tags
            text_clean = re.sub(r'#+\s+', '', text)
            text_clean = re.sub(r'[*_\-`]', '', text_clean)
            return len(text_clean.split())

        en_word_count = clean_word_count(en_content)
        el_word_count = clean_word_count(el_content)

        if en_word_count < 300 or en_word_count > 500:
            errors.append(f"English content word count is outside 300-500 words limit (current: {en_word_count}).")
        if el_word_count < 300 or el_word_count > 500:
            errors.append(f"Greek content word count is outside 300-500 words limit (current: {el_word_count}).")

        # 7. LLM-assisted Greek medical translation check
        if self.client and not errors:
            greek_check_errors = self._check_greek_terminology_and_flow(en_content, el_content)
            errors.extend(greek_check_errors)

        return len(errors) == 0, errors

    def _check_greek_terminology_and_flow(self, en_content, el_content):
        """Uses Gemini to perform a clinical and stylistic check on the Greek translation."""
        system_instruction = (
            "You are an expert Greek Medical Quality Assurance Editor. Your job is to check dental "
            "translations to ensure they use correct Greek clinical terms and read naturally."
        )

        prompt = f"""
Compare the following English dental blog content with its Greek translation.

**English Content:**
\"\"\"
{en_content}
\"\"\"

**Greek Translation:**
\"\"\"
{el_content}
\"\"\"

Verify that:
1. Important dental concepts are correctly translated (e.g., 'osseointegration' -> 'οστεοενσωμάτωση', 'peri-implantitis' -> 'περιεμφυτευματίτιδα', 'apical periodontitis' -> 'ακρορριζική περιοδοντίτιδα').
2. The Greek text does not have grammar mistakes or awkward literal phrasing.
3. The style remains professional, empathetic, and medically credible.

Output your assessment as a JSON object:
{{
  "is_valid": <true or false>,
  "errors": [
     "Detail specific translation/clinical terminology errors or awkward phrasings found here. If valid, leave this list empty."
  ]
}}
"""
        try:
            response_text = self.run_llm(
                prompt=prompt,
                system_instruction=system_instruction,
                mime_type="application/json"
            )
            report = json.loads(response_text)
            if not report.get("is_valid", True):
                return report.get("errors", [])
        except Exception as e:
            print(f"[QAAgent] Warning: Terminology check failed to run: {e}")
            
        return []
