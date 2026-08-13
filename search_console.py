"""Small, credential-safe Google Search Console integration and opportunity model."""
from __future__ import annotations

import json
import math
import os
import re
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

SITE_URL_ENV = "SEARCH_CONSOLE_SITE_URL"
SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "search_console_snapshot.json"
WINDOW_DAYS = 28
MAX_QUERY_ROWS = 100
MIN_MEANINGFUL_IMPRESSIONS = 20
ALLOWED_HOSTS = {"dentplant.gr", "www.dentplant.gr"}


def comparison_windows(today=None):
    """Two complete, non-overlapping 28-day windows; excludes today."""
    today = today or date.today()
    recent_end = today - timedelta(days=1)
    recent_start = recent_end - timedelta(days=WINDOW_DAYS - 1)
    previous_end = recent_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=WINDOW_DAYS - 1)
    return ({"start_date": recent_start.isoformat(), "end_date": recent_end.isoformat()},
            {"start_date": previous_start.isoformat(), "end_date": previous_end.isoformat()})


def normalize_dentplant_url(value, site_url=None):
    """Convert an internal absolute URL to content-map path, else return None."""
    if not value:
        return None
    parsed = urlparse(str(value))
    if parsed.scheme and parsed.hostname and parsed.hostname.lower() not in ALLOWED_HOSTS:
        return None
    if not parsed.scheme and parsed.netloc and parsed.netloc.lower() not in ALLOWED_HOSTS:
        return None
    path = (parsed.path or "").lstrip("/")
    if path in {"", "index.html"}:
        return "index.html"
    return path.rstrip("/") or "index.html"


def _metrics(row):
    return {"clicks": float(row.get("clicks", 0) or 0), "impressions": float(row.get("impressions", 0) or 0),
            "ctr": float(row.get("ctr", 0) or 0), "position": float(row.get("position", 0) or 0)}


def _score(value): return round(max(0, min(10, value)), 2)

def opportunity_scores(recent, previous=None, relevance=0):
    """Bounded deterministic scores. Low samples never create large opportunities."""
    r, p = _metrics(recent), _metrics(previous or {})
    impressions = r["impressions"]
    sample = min(1.0, impressions / MIN_MEANINGFUL_IMPRESSIONS)
    demand = _score(math.log1p(impressions) / math.log(501) * 10 * max(relevance, 0) / 10)
    position = r["position"]
    if 4 <= position <= 20:
        ranking = _score((10 - abs(10 - position) * 0.45) * sample)
    else:
        ranking = _score((2 if 0 < position <= 3 else 1) * sample)
    expected_ctr = 0.30 if position <= 3 else 0.18 if position <= 10 else 0.10 if position <= 20 else 0.05
    ctr = _score(max(0, expected_ctr - r["ctr"]) / expected_ctr * 10 * sample)
    if p["impressions"] < MIN_MEANINGFUL_IMPRESSIONS or impressions < MIN_MEANINGFUL_IMPRESSIONS:
        trend = 0
    else:
        trend = _score(((impressions - p["impressions"]) / max(p["impressions"], 1)) * 5 + 5)
    return {"search_demand": demand, "ctr_opportunity": ctr, "ranking_opportunity": ranking, "trend": trend}


def query_relevance(query, candidate_text, mapped_pages=()):
    query_tokens = set(re.findall(r"[\w-]+", (query or "").lower()))
    candidate_tokens = set(re.findall(r"[\w-]+", (candidate_text or "").lower()))
    page_tokens = set(re.findall(r"[\w-]+", " ".join(mapped_pages).lower().replace("-", " ")))
    if not query_tokens: return 0
    return _score(10 * len(query_tokens & (candidate_tokens | page_tokens)) / len(query_tokens))


def build_snapshot(site_url, recent_rows, previous_rows, today=None):
    recent_window, comparison_window = comparison_windows(today)
    previous_by_key = {(tuple(row.get("keys", []))): row for row in previous_rows}
    pages, queries = {}, []
    for row in recent_rows:
        keys = row.get("keys", [])
        if len(keys) != 2: continue
        query, raw_page = keys
        path = normalize_dentplant_url(raw_page, site_url)
        if not path: continue
        current = _metrics(row)
        prior = _metrics(previous_by_key.get(tuple(keys), {}))
        if current["impressions"] < 1: continue
        entry = {"query": str(query), "page": path, **current, "previous": prior}
        queries.append(entry)
        page = pages.setdefault(path, {"clicks": 0, "impressions": 0, "weighted_position": 0})
        page["clicks"] += current["clicks"]; page["impressions"] += current["impressions"]
        page["weighted_position"] += current["position"] * current["impressions"]
    queries.sort(key=lambda q: (-q["impressions"], q["query"], q["page"]))
    for page in pages.values():
        page["ctr"] = page["clicks"] / page["impressions"] if page["impressions"] else 0
        page["position"] = page.pop("weighted_position") / page["impressions"] if page["impressions"] else 0
    return {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(), "site_url": site_url,
            "recent_window": recent_window, "comparison_window": comparison_window, "pages": pages, "queries": queries[:MAX_QUERY_ROWS]}


def save_snapshot(snapshot, path=SNAPSHOT_PATH):
    safe = {key: snapshot.get(key) for key in ("schema_version", "generated_at", "site_url", "recent_window", "comparison_window", "pages", "queries")}
    Path(path).write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return safe


def load_snapshot(path=SNAPSHOT_PATH):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if data.get("schema_version") == 1 else None
    except (OSError, json.JSONDecodeError): return None


def fetch_snapshot_from_api(site_url=None, today=None):
    """Fetch only query+page metric rows. Missing auth is a non-fatal None result."""
    site_url = site_url or os.getenv(SITE_URL_ENV)
    if not site_url:
        print("[SearchConsole] Performance signals unavailable: SEARCH_CONSOLE_SITE_URL is not configured.")
        return None
    try:
        from google.auth import default
        from googleapiclient.discovery import build
        credentials, _ = default(scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
        service = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)
        recent, previous = comparison_windows(today)
        def query(window):
            return service.searchanalytics().query(siteUrl=site_url, body={
                "startDate": window["start_date"], "endDate": window["end_date"], "dimensions": ["query", "page"], "rowLimit": MAX_QUERY_ROWS,
            }).execute().get("rows", [])
        return build_snapshot(site_url, query(recent), query(previous), today)
    except Exception as exc:
        print(f"[SearchConsole] Performance signals unavailable; continuing without them ({type(exc).__name__}).")
        return None


def get_performance_snapshot(required=False):
    snapshot = fetch_snapshot_from_api()
    if snapshot:
        save_snapshot(snapshot); return snapshot
    if required:
        raise RuntimeError("Search Console is required but performance signals are unavailable.")
    return load_snapshot()
