"""Fail-closed parsing and rendering of ContentBrief internal-link directives."""

from __future__ import annotations

import json
import posixpath
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


CONTENT_MAP_PATH = Path(__file__).resolve().parent / "data" / "dentplant_content_map.json"
PLAN_HEADER = "--- INTERNAL LINK PLAN ---"
FIELD_PATTERN = re.compile(r"^\[LINK_(\d+)_(TARGET|ANCHOR_EN|ANCHOR_EL|CONTEXT_EN|CONTEXT_EL)\]:\s*(.*)$")


class LinkPlanValidationError(ValueError):
    """A plan cannot safely become article HTML."""


def load_content_map(path=CONTENT_MAP_PATH):
    with Path(path).open(encoding="utf-8") as handle:
        content_map = json.load(handle)
    return content_map


def normalize_target_path(target):
    if not isinstance(target, str) or not target.strip():
        raise LinkPlanValidationError("Internal-link target is empty.")
    target = target.strip()
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or target.startswith("//"):
        raise LinkPlanValidationError(f"Internal-link target must be a relative path: {target}")
    if parsed.query or parsed.fragment or "\\" in target or target.startswith("/"):
        raise LinkPlanValidationError(f"Internal-link target is not normalized: {target}")
    normalized = posixpath.normpath(parsed.path)
    if normalized.startswith("../") or normalized in {".", ".."} or normalized != parsed.path:
        raise LinkPlanValidationError(f"Internal-link target contains path traversal: {target}")
    return normalized


def parse_link_plan(markdown):
    """Parse only the exact trailing directive schema emitted by CopywriterAgent."""
    parts = markdown.split(PLAN_HEADER)
    if len(parts) != 2:
        raise LinkPlanValidationError("Expected exactly one internal-link plan section.")
    plan_text = parts[1].strip()
    if not plan_text:
        raise LinkPlanValidationError("Internal-link plan section is empty.")
    entries = {}
    for line in plan_text.splitlines():
        if not line.strip():
            continue
        match = FIELD_PATTERN.fullmatch(line)
        if not match:
            raise LinkPlanValidationError(f"Malformed internal-link directive: {line}")
        number, field, value = match.groups()
        entry = entries.setdefault(int(number), {})
        if field in entry:
            raise LinkPlanValidationError(f"Duplicate {field} directive for link {number}.")
        entry[field] = value.strip()
    ordered = []
    for number in sorted(entries):
        entry = entries[number]
        required = {"TARGET", "ANCHOR_EN", "ANCHOR_EL", "CONTEXT_EN", "CONTEXT_EL"}
        if set(entry) != required:
            raise LinkPlanValidationError(f"Link {number} does not contain the required directive fields.")
        if not entry["ANCHOR_EN"] or not entry["ANCHOR_EL"]:
            raise LinkPlanValidationError(f"Link {number} has an empty bilingual anchor pair.")
        ordered.append({"target_path": normalize_target_path(entry["TARGET"]), "anchor_en": entry["ANCHOR_EN"], "anchor_el": entry["ANCHOR_EL"], "context_en": entry["CONTEXT_EN"], "context_el": entry["CONTEXT_EL"]})
    return ordered


def validate_link_plan(plan, content_brief, content_map=None):
    content_map = content_map or load_content_map()
    map_paths = {page.get("path") for page in content_map.get("pages", [])}
    approved = content_brief.get("recommended_internal_links") or []
    if not approved:
        raise LinkPlanValidationError("ContentBrief does not authorize internal links.")
    approved_by_target = {}
    for link in approved:
        target = normalize_target_path(link.get("target_path", ""))
        if target in approved_by_target:
            raise LinkPlanValidationError(f"ContentBrief contains a duplicate target: {target}")
        approved_by_target[target] = link

    seen = set()
    for link in plan:
        target = link["target_path"]
        if target in seen:
            raise LinkPlanValidationError(f"Duplicate target in generated plan: {target}")
        seen.add(target)
        if target not in map_paths:
            raise LinkPlanValidationError(f"Target is absent from Dentplant content map: {target}")
        expected = approved_by_target.get(target)
        if not expected:
            raise LinkPlanValidationError(f"Target is not authorized by ContentBrief: {target}")
        if link["anchor_en"] != expected.get("anchor_en") or link["anchor_el"] != expected.get("anchor_el"):
            raise LinkPlanValidationError(f"Anchor pair does not match ContentBrief for target: {target}")

    if set(seen) != set(approved_by_target):
        raise LinkPlanValidationError("Generated plan does not contain exactly the ContentBrief targets.")
    return plan


def _replace_anchor_once(markdown, anchor, href):
    """Replace one natural prose occurrence; headings and existing links are off limits."""
    if not anchor:
        raise LinkPlanValidationError("Cannot insert an empty anchor.")
    escaped = re.escape(anchor)
    for match in re.finditer(rf"(?<![\w]){escaped}(?![\w])", markdown):
        line_start = markdown.rfind("\n", 0, match.start()) + 1
        line_end = markdown.find("\n", match.end())
        line_end = len(markdown) if line_end == -1 else line_end
        line = markdown[line_start:line_end]
        if re.match(r"\s*#{1,6}\s", line) or "<a " in line.lower():
            continue
        before = line[:match.start() - line_start]
        after = line[match.end() - line_start:]
        # A Markdown link's visible text or destination must not be nested/reused.
        if before.rfind("[") > before.rfind("](") or "](" in after.split(" ", 1)[0]:
            continue
        replacement = f"[{anchor}]({href})"
        return markdown[:match.start()] + replacement + markdown[match.end():]
    raise LinkPlanValidationError(f"Approved anchor was not found in safe prose: {anchor}")


def _content_sections(markdown):
    plan_index = markdown.index(PLAN_HEADER)
    article = markdown[:plan_index].rstrip()
    en_match = re.search(r"(\[EN_CONTENT\]:\s*\n)(.*?)(?=\n--- GREEK VERSION ---)", article, re.DOTALL)
    el_match = re.search(r"(\[EL_CONTENT\]:\s*\n)(.*)$", article, re.DOTALL)
    if not en_match or not el_match:
        raise LinkPlanValidationError("Article lacks parseable bilingual content sections.")
    return article, en_match, el_match


def render_internal_links(markdown, content_brief, content_map=None):
    """Return safe link-rendered Markdown plus a compact validation report."""
    plan = validate_link_plan(parse_link_plan(markdown), content_brief, content_map)
    article, en_match, el_match = _content_sections(markdown)
    en_content, el_content = en_match.group(2), el_match.group(2)
    for link in plan:
        href = f"../{link['target_path']}"
        en_content = _replace_anchor_once(en_content, link["anchor_en"], href)
        el_content = _replace_anchor_once(el_content, link["anchor_el"], href)

    rendered = article[:en_match.start(2)] + en_content + article[en_match.end(2):el_match.start(2)] + el_content
    report = validate_rendered_links(rendered, plan)
    return rendered, report


class _AnchorCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._current = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            if self._current is not None:
                raise LinkPlanValidationError("Nested anchors were rendered.")
            self._current = {"href": dict(attrs).get("href", ""), "text": ""}

    def handle_data(self, data):
        if self._current is not None:
            self._current["text"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self._current is not None:
            self.links.append(self._current)
            self._current = None


def _render_markdown(markdown):
    try:
        import markdown as markdown_library
    except ImportError as exc:
        raise LinkPlanValidationError("Markdown renderer is unavailable for link validation.") from exc
    return markdown_library.markdown(markdown)


def validate_rendered_links(markdown, plan):
    article, en_match, el_match = _content_sections(markdown + "\n" + PLAN_HEADER) if PLAN_HEADER not in markdown else _content_sections(markdown)
    # render_internal_links passes no plan header in its working article; use sections directly below.
    _ = article
    sections = {"en": en_match.group(2), "el": el_match.group(2)}
    expected = {f"../{link['target_path']}": link for link in plan}
    report = {"valid": True, "links": {"en": [], "el": []}}
    for language, section in sections.items():
        parser = _AnchorCollector()
        parser.feed(_render_markdown(section))
        internal = [link for link in parser.links if link["href"].startswith("../") or "dentplant.gr" in link["href"]]
        if len(internal) != len(plan):
            raise LinkPlanValidationError(f"{language} article does not contain exactly the approved internal link set.")
        for link in internal:
            if link["href"] not in expected:
                raise LinkPlanValidationError(f"{language} article contains an unapproved internal link: {link['href']}")
            expected_anchor = expected[link["href"]][f"anchor_{language}"]
            if link["text"] != expected_anchor:
                raise LinkPlanValidationError(f"{language} rendered anchor does not match approved text for {link['href']}")
            report["links"][language].append({"href": link["href"], "text": link["text"]})
    return report
