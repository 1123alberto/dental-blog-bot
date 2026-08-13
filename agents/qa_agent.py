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

    def validate_post(self, markdown_content, practice_name="Dentplant", content_brief=None):
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
        el_content = get_field(r"\[EL_CONTENT\]:", r"--- INTERNAL LINK PLAN ---")

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

        if content_brief:
            errors.extend(self._validate_content_brief_compliance(markdown_content, en_content, el_content, content_brief))

        # 7. LLM-assisted Greek medical translation check
        if self.client and not errors:
            greek_check_errors = self._check_greek_terminology_and_flow(en_content, el_content)
            errors.extend(greek_check_errors)

        return len(errors) == 0, errors

    def _validate_content_brief_compliance(self, markdown_content, en_content, el_content, content_brief):
        """Lightweight offline checks for deterministic brief/link-plan compliance."""
        errors = []
        primary_intent = str(content_brief.get("primary_patient_intent", "")).lower()
        angle = str(content_brief.get("article_angle", "")).lower()
        combined = f"{en_content} {el_content}".lower()
        intent_terms = [term for term in re.findall(r"[a-z]{4,}", primary_intent) if term not in {"general", "health"}]
        angle_terms = [term for term in re.findall(r"[a-z]{5,}", angle) if term not in {"study", "source"}]
        if intent_terms and not any(term in combined for term in intent_terms) and angle_terms and not any(term in combined for term in angle_terms):
            errors.append("Article does not visibly address the ContentBrief patient intent or article angle.")

        maturity = content_brief.get("evidence_maturity", "")
        if maturity in {"early research", "laboratory/preclinical research"}:
            cautious_terms = ("preliminary", "early", "laboratory", "further research", "προκαταρκ", "εργαστηρια", "περαιτέρω")
            if not any(term in combined for term in cautious_terms):
                errors.append("Research maturity is not expressed cautiously in both language versions.")
        if maturity == "emerging clinical adoption":
            emerging_terms = ("emerging", "increasingly studied", "not yet universal", "αναδυ", "υπό μελέτη", "όχι ακόμη")
            if not any(term in combined for term in emerging_terms):
                errors.append("Emerging evidence maturity is not preserved in the article.")

        supplied_statistics = " ".join(
            claim.get("evidence_excerpt", "") for claim in content_brief.get("claims", [])
        )
        article_statistics = re.findall(r"\b\d+(?:[.,]\d+)?\s*(?:%|percent(?:age)?|ποσοστ\w*)", f"{en_content} {el_content}", re.IGNORECASE)
        for statistic in article_statistics:
            normalized = re.sub(r"\s+", "", statistic).replace(",", ".").lower()
            normalized_source = supplied_statistics.replace(" ", "").replace(",", ".").lower()
            if normalized not in normalized_source:
                errors.append(f"Unsupported statistic introduced outside ContentBrief claims: {statistic}")

        combined_source = f"{en_content} {el_content}"
        self._append_medical_safety_errors(errors, combined_source, content_brief)

        planned_links = content_brief.get("recommended_internal_links", [])
        plan_section = re.search(r"--- INTERNAL LINK PLAN ---\s*(.*)$", markdown_content, re.DOTALL | re.IGNORECASE)
        if planned_links and not plan_section:
            errors.append("Missing required internal-link plan section from ContentBrief.")
            return errors
        if plan_section:
            fields = {
                (index, field): value.strip()
                for index, field, value in re.findall(
                    r"\[LINK_(\d+)_(TARGET|ANCHOR_EN|ANCHOR_EL)\]:\s*(.*)", plan_section.group(1)
                )
            }
            expected = {str(index): link for index, link in enumerate(planned_links, 1)}
            if set(key for key, field in fields if field == "TARGET") != set(expected):
                errors.append("Internal-link plan targets do not match the ContentBrief exactly.")
            for index, link in expected.items():
                if fields.get((index, "TARGET")) != link.get("target_path"):
                    errors.append(f"Internal-link target {index} is not the planned Dentplant path.")
                if fields.get((index, "ANCHOR_EN")) != link.get("anchor_en") or fields.get((index, "ANCHOR_EL")) != link.get("anchor_el"):
                    errors.append(f"Internal-link anchors {index} are not aligned with the ContentBrief.")

        if content_brief.get("clinical_risk_notes"):
            proportional_terms = ("risk", "proportion", "prevention", "warning", "κίνδυν", "πρόληψ", "προειδοπ")
            if not any(term in combined for term in proportional_terms):
                errors.append("Clinical-risk ContentBrief guidance is not reflected proportionately.")
        return errors

    def _append_medical_safety_errors(self, errors, article_text, content_brief):
        """Focused deterministic safeguards; these complement, never imply, human review."""
        text = article_text.lower()
        absolute_patterns = (
            r"\b(guaranteed|guarantee|zero[- ]risk|no risk|risk[- ]free|lifetime success|permanent success|completely painless|universally safe|no complications)\b",
            r"(εγγυημέν\w*|μηδενικ\w*\s+κίνδυν\w*|χωρίς\s+κίνδυν\w*|δια\s+βίου\s+επιτυχ\w*|μόνιμ\w*\s+επιτυχ\w*|εντελώς\s+ανώδυν\w*|απόλυτα\s+ασφαλ\w*|χωρίς\s+επιπλοκ\w*)",
        )
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in absolute_patterns):
            errors.append("Absolute or zero-risk treatment claim is not permitted.")

        oral_systemic = any(term in text for term in ("diabetes", "cardiovascular", "heart disease", "systemic", "διαβήτη", "καρδιαγγεια", "συστηματικ"))
        causal = re.search(r"\b(causes?|proves? that .* causes?|directly causes?|αιτι\w*|προκαλεί)\b", text, re.IGNORECASE)
        claims_text = " ".join(item.get("claim", "") for item in content_brief.get("claims", [])).lower()
        if oral_systemic and causal and not re.search(r"\b(causes?|causal|αιτι\w*|προκαλεί)\b", claims_text, re.IGNORECASE):
            errors.append("Association-to-causation overstatement is unsupported by the ContentBrief.")

        maturity = content_brief.get("evidence_maturity", "")
        if maturity in {"early research", "laboratory/preclinical research", "emerging clinical adoption"} and re.search(
            r"\b(standard (?:treatment|care)|routine care|established clinical protocol|universally available|καθιερωμέν\w* (?:θεραπεία|φροντίδα)|τυπικ\w* θεραπεία|πρωτόκολλ\w* ρουτίνας)\b", text, re.IGNORECASE
        ):
            errors.append("Early or emerging evidence cannot be described as standard or routine care.")

        availability = re.search(r"(?:dentplant|η\s*dentplant)\s+(?:offers|uses|provides|routinely performs|προσφέρει|χρησιμοποιεί|παρέχει|εφαρμόζει)\s+([^.!?]+)", article_text, re.IGNORECASE)
        if availability:
            offered = availability.group(1).strip().lower()
            mapped = " ".join(str(page) for page in content_brief.get("related_dentplant_pages", [])) + " " + " ".join(
                link.get("anchor_en", "") + " " + link.get("anchor_el", "") for link in content_brief.get("recommended_internal_links", [])
            )
            if offered not in mapped.lower():
                errors.append("Practice-specific Dentplant treatment or technology availability is unsupported by the content map.")

        if content_brief.get("clinical_risk_topic"):
            has_risk = any(term in text for term in ("risk", "complication", "κίνδυν", "επιπλοκ"))
            has_context = any(term in text for term in ("prevention", "monitor", "assessment", "consult", "πρόληψ", "παρακολούθ", "αξιολόγ", "εξέταση"))
            if not (has_risk and has_context):
                errors.append("Clinical-risk topic needs proportionate risk context and prevention, monitoring, or assessment guidance.")
        if re.search(r"\b(diagnose|replace (?:an )?examination|guarantee candidacy|determine candidacy|διαγνώσ\w*|αντικαθιστά\s+(?:την\s+)?εξέταση|εγγυάται\s+(?:την\s+)?καταλληλ)\b", text, re.IGNORECASE):
            errors.append("Article wording exceeds patient-education and diagnostic boundaries.")

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
