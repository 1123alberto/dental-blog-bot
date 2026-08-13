#!/usr/bin/env python3
"""Build a deterministic, structure-only content inventory for Dentplant.

The website checkout is never modified.  Set WEBSITE_PATH to select a checkout;
the legacy local checkout path is used only when the variable is not set.
"""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import sys
from collections import Counter, defaultdict
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_WEBSITE_PATH = Path.home() / "Gemini" / "dentplant-new"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "data" / "dentplant_content_map.json"
EXCLUDED_DIRS = {".git", "node_modules", "tests", "test", "fixtures", "fixture", "tmp", "temp", "dist", "build"}
EXCLUDED_NAMES = {"404.html", "500.html", "error.html", "manage.html"}
TREATMENT_HUBS = {
    "implants.html", "oral-surgery.html", "aesthetics.html", "clear-aligners.html", "treatments.html"
}
DETAIL_PREFIX_PARENTS = {
    "implant-": "implants.html",
    "surgery-": "oral-surgery.html",
    "treatment-": "treatments.html",
}
DETAIL_FILE_PARENTS = {
    "teeth-whitening.html": "aesthetics.html",
    "porcelain-veneers.html": "aesthetics.html",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


class PageParser(HTMLParser):
    """Small stdlib parser for the metadata, headings, and anchors we need."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.attrs: dict[str, str] = {}
        self.title = ""
        self.description = ""
        self.canonical_url = ""
        self.lang = ""
        self.robots = ""
        self.headings: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}
        self.links: list[str] = []
        self._active_text_tag: str | None = None
        self._text_parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): (value or "") for key, value in attrs}
        if tag == "html":
            self.lang = attributes.get("lang", "")
        elif tag == "meta":
            name = attributes.get("name", "").lower()
            if name == "description":
                self.description = attributes.get("content", "")
            elif name == "robots":
                self.robots = attributes.get("content", "")
        elif tag == "link" and "canonical" in attributes.get("rel", "").lower().split():
            self.canonical_url = attributes.get("href", "")
        elif tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"])
        if tag in {"script", "style", "noscript"}:
            self._ignored_depth += 1
        if tag == "title" or tag in self.headings:
            self._active_text_tag = tag
            self._text_parts = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self._active_text_tag and not self._ignored_depth:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == self._active_text_tag:
            text = clean_text("".join(self._text_parts))
            if tag == "title":
                self.title = text
            elif text:
                self.headings[tag].append(text)
            self._active_text_tag = None
            self._text_parts = []
        if tag in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1


def normalized_url(raw_url: str, base_url: str, internal_hosts: set[str]) -> str | None:
    """Return a canonical-form internal URL, excluding non-page URI schemes."""
    raw_url = raw_url.strip()
    if not raw_url or raw_url.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return None
    parsed = urlsplit(urljoin(base_url, raw_url))
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in internal_hosts:
        return None
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path.endswith("/index.html"):
        path = path[: -len("index.html")]
    if not path:
        path = "/"
    return urlunsplit(("https", "www.dentplant.gr", path, "", ""))


def canonical_for_path(relative_path: str, site_base_url: str) -> str:
    path = "/" if relative_path == "index.html" else f"/{relative_path}"
    return normalized_url(path, site_base_url, {"dentplant.gr", "www.dentplant.gr"}) or site_base_url


def page_type(relative_path: str) -> str:
    name = Path(relative_path).name
    if name == "index.html":
        return "homepage"
    if name in TREATMENT_HUBS:
        return "treatment hub"
    if name == "about.html":
        return "doctor/about"
    if name in {"contact.html", "booking.html"}:
        return "contact/location"
    if relative_path.startswith("article/news-"):
        return "news/blog article"
    if name.startswith("article-"):
        return "informational article"
    if name.startswith(("implant-", "surgery-", "treatment-")) or name in DETAIL_FILE_PARENTS:
        return "treatment detail"
    if name in {"blog.html", "privacy.html", "disclaimer.html"}:
        return "utility/other"
    return "unknown"


def likely_content_file(path: Path, website_path: Path) -> bool:
    relative = path.relative_to(website_path)
    if path.name.lower() in EXCLUDED_NAMES:
        return False
    return not any(part.lower() in EXCLUDED_DIRS or part.startswith(".") for part in relative.parts)


def sitemap_urls(website_path: Path, site_base_url: str, internal_hosts: set[str]) -> set[str]:
    sitemap_path = website_path / "sitemap.xml"
    if not sitemap_path.is_file():
        return set()
    try:
        root = ElementTree.parse(sitemap_path).getroot()
    except ElementTree.ParseError as exc:
        raise ValueError(f"Cannot parse sitemap: {exc}") from exc
    urls = set()
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == "loc" and element.text:
            normalized = normalized_url(element.text, site_base_url, internal_hosts)
            if normalized:
                urls.add(normalized)
    return urls


def parent_path_for(relative_path: str) -> str | None:
    name = Path(relative_path).name
    if name in DETAIL_FILE_PARENTS:
        return DETAIL_FILE_PARENTS[name]
    for prefix, parent in DETAIL_PREFIX_PARENTS.items():
        if name.startswith(prefix):
            return parent
    if relative_path.startswith("article/article-aligners-"):
        return "clear-aligners.html"
    return None


def build_map(website_path: Path) -> tuple[dict, dict]:
    if not website_path.is_dir():
        raise FileNotFoundError(f"Website path does not exist: {website_path}")
    html_files = sorted(website_path.rglob("*.html"), key=lambda file: file.as_posix())
    scanned_count = len(html_files)
    parsed_pages: list[tuple[str, PageParser]] = []
    for file_path in html_files:
        if not likely_content_file(file_path, website_path):
            continue
        parser = PageParser()
        parser.feed(file_path.read_text(encoding="utf-8", errors="replace"))
        parser.close()
        if "noindex" not in parser.robots.lower():
            parsed_pages.append((file_path.relative_to(website_path).as_posix(), parser))

    site_base_url = "https://www.dentplant.gr/"
    for _, parser in parsed_pages:
        if parser.canonical_url:
            parsed = urlsplit(parser.canonical_url)
            if parsed.scheme and parsed.netloc:
                site_base_url = urlunsplit((parsed.scheme, parsed.netloc, "/", "", ""))
                break
    internal_hosts = {"dentplant.gr", "www.dentplant.gr", urlsplit(site_base_url).netloc.lower()}
    sitemap = sitemap_urls(website_path, site_base_url, internal_hosts)

    pages = []
    for relative_path, parser in parsed_pages:
        source_url = canonical_for_path(relative_path, site_base_url)
        canonical_url = normalized_url(parser.canonical_url, source_url, internal_hosts) if parser.canonical_url else ""
        outgoing = sorted({target for href in parser.links if (target := normalized_url(href, source_url, internal_hosts))})
        kind = page_type(relative_path)
        pages.append({
            "path": relative_path,
            "canonical_url": canonical_url,
            "title": parser.title,
            "meta_description": parser.description,
            "h1": parser.headings["h1"],
            "h2": parser.headings["h2"],
            "h3": parser.headings["h3"],
            "language": parser.lang or None,
            "page_type": kind,
            "is_treatment_page": kind in {"treatment hub", "treatment detail"},
            "is_article": kind in {"informational article", "news/blog article"},
            "is_priority_candidate": kind in {"homepage", "treatment hub", "treatment detail", "informational article"},
            "outbound_internal_links": outgoing,
            "linked_dentplant_pages": [],
            "internal_link_count": len(outgoing),
            "inbound_link_count": 0,
            "parent_candidates": [],
            "child_candidates": [],
            "in_sitemap": canonical_url in sitemap if canonical_url else False,
        })

    pages.sort(key=lambda page: page["path"])
    by_url = {page["canonical_url"]: page for page in pages if page["canonical_url"]}
    for page in pages:
        linked = sorted(url for url in page["outbound_internal_links"] if url in by_url)
        page["linked_dentplant_pages"] = linked
        for target in linked:
            by_url[target]["inbound_link_count"] += 1

    for page in pages:
        expected_parent = parent_path_for(page["path"])
        if expected_parent:
            parent_url = canonical_for_path(expected_parent, site_base_url)
            if parent_url in page["linked_dentplant_pages"]:
                page["parent_candidates"] = [parent_url]
        if page["page_type"] == "treatment hub":
            children = []
            for target_url in page["linked_dentplant_pages"]:
                target = by_url[target_url]
                if parent_path_for(target["path"]) == page["path"]:
                    children.append(target_url)
            page["child_candidates"] = sorted(children)

    duplicate_canonicals = sorted(url for url, count in Counter(page["canonical_url"] for page in pages if page["canonical_url"]).items() if count > 1)
    validation = {
        "html_pages_scanned": scanned_count,
        "pages_included": len(pages),
        "pages_by_type": dict(sorted(Counter(page["page_type"] for page in pages).items())),
        "pages_missing_canonical_url": [page["path"] for page in pages if not page["canonical_url"]],
        "pages_missing_h1": [page["path"] for page in pages if not page["h1"]],
        "pages_missing_meta_description": [page["path"] for page in pages if not page["meta_description"]],
        "pages_not_in_sitemap": [page["path"] for page in pages if not page["in_sitemap"]],
        "duplicate_page_paths": [],
        "duplicate_canonical_urls": duplicate_canonicals,
        "top_10_by_inbound_internal_link_count": [
            {"path": page["path"], "canonical_url": page["canonical_url"], "inbound_link_count": page["inbound_link_count"]}
            for page in sorted(pages, key=lambda item: (-item["inbound_link_count"], item["path"]))[:10]
        ],
    }
    content_map = {
        "schema_version": "1.0",
        "source": {"site_base_url": site_base_url, "sitemap_path": "sitemap.xml"},
        "normalization": {"internal_urls": "https://www.dentplant.gr with no query string, fragment, or /index.html suffix"},
        "pages": pages,
    }
    return content_map, validation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--website-path", type=Path, default=Path(os.environ.get("WEBSITE_PATH", DEFAULT_WEBSITE_PATH)))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()
    try:
        content_map, validation = build_map(args.website_path.expanduser().resolve())
    except (FileNotFoundError, ValueError) as exc:
        print(f"content map generation failed: {exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(content_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
