"""
sources/luma.py — PRIMARY source: lu.ma event aggregator.

Two strategies (both used; results merged):

1. Discover API (undocumented public JSON endpoint):
   GET https://api.lu.ma/discover/get-paginated-events?query=<city>&pagination_limit=50
   Called for each query term in DISCOVER_QUERIES.

2. Embedded __NEXT_DATA__ JSON in HTML pages:
   Fetch https://lu.ma/<slug> for each slug in PAGE_SLUGS.
   Parse the <script id="__NEXT_DATA__"> tag and walk the event tree.

source_name = "luma"
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from eventradar import config
from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "luma"

DISCOVER_API = "https://api.lu.ma/discover/get-paginated-events"
DISCOVER_QUERIES = ["hyderabad", "bangalore", "india", "startup", "tech", "hackathon"]

PAGE_SLUGS = [
    "hyderabad",
    "blr",
    "t-hub",
    "aicamp",
    "techindia",
    "startupindia",
    "genai-india",
]

# Slug -> scope mapping
_SLUG_SCOPE: dict[str, str] = {
    "hyderabad":    "hyderabad",
    "blr":          "india",
    "t-hub":        "hyderabad",
    "aicamp":       "india",
    "techindia":    "india",
    "startupindia": "india",
    "genai-india":  "india",
}

_QUERY_SCOPE: dict[str, str] = {
    "hyderabad":  "hyderabad",
    "bangalore":  "india",
    "india":      "india",
    "startup":    "global",
    "tech":       "global",
    "hackathon":  "global",
}

_LUMA_HEADERS = {
    "Accept": "application/json",
    "Origin": "https://lu.ma",
    "Referer": "https://lu.ma/",
}


# ─── helpers ──────────────────────────────────────────────────────────────────

def _scope_for_query(query: str) -> str:
    return _QUERY_SCOPE.get(query.lower(), "global")


def _scope_for_slug(slug: str) -> str:
    return _SLUG_SCOPE.get(slug.lower(), "global")


def _safe_str(obj: Any, *keys: str) -> str | None:
    """Walk nested dicts safely and return a string or None."""
    cur: Any = obj
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    if cur is None:
        return None
    return str(cur).strip() or None


def _extract_event(raw: dict[str, Any], scope: str) -> dict[str, Any] | None:
    """Convert a single Luma raw event dict into our intermediate schema dict."""
    # Luma events can be nested under an "event" key
    ev = raw.get("event") or raw

    title = _safe_str(ev, "name") or _safe_str(ev, "title")
    if not title:
        return None

    # Registration URL: prefer url, fall back to slug
    url = _safe_str(ev, "url")
    slug = _safe_str(ev, "slug") or _safe_str(ev, "api_id")
    if not url and slug:
        url = f"https://lu.ma/{slug}"
    if not url:
        return None

    event_id = _safe_str(ev, "api_id") or _safe_str(ev, "id") or slug
    if not event_id:
        event_id = slug or url.split("/")[-1]

    description = _safe_str(ev, "description") or _safe_str(ev, "description_short")
    start_at = _safe_str(ev, "start_at") or _safe_str(ev, "start_date")
    end_at = _safe_str(ev, "end_at") or _safe_str(ev, "end_date")

    # Mode
    geo_address = ev.get("geo_address_info") or {}
    location_type = (
        _safe_str(ev, "location_type")
        or _safe_str(ev, "event_type_for_display")
        or ""
    ).lower()
    if "online" in location_type or "virtual" in location_type:
        mode = "online"
    elif geo_address:
        mode = "offline"
    else:
        mode = None

    # Venue / City
    city_name = (
        _safe_str(geo_address, "city")
        or _safe_str(ev, "city")
        or ""
    ).lower()
    city = None
    if "hyderabad" in city_name:
        city = "hyderabad"
        scope = "hyderabad"
    elif "bangalore" in city_name or "bengaluru" in city_name:
        city = "bangalore"

    venue = _safe_str(geo_address, "full_address") or _safe_str(ev, "location")

    # Organizer
    host = ev.get("hosts") or []
    organizer = None
    if isinstance(host, list) and host:
        organizer = _safe_str(host[0], "name") if isinstance(host[0], dict) else None
    if not organizer:
        organizer = _safe_str(ev, "organizer_name") or _safe_str(ev, "calendar_name")

    # Tickets / free?
    tickets = ev.get("ticket_info") or {}
    is_free: bool | None = None
    if tickets:
        price = tickets.get("min_price") or tickets.get("price")
        if price is not None:
            is_free = float(price) == 0.0

    # Cover image check (unused but good for future)
    tags: list[str] = []
    raw_tags = ev.get("tags") or []
    if isinstance(raw_tags, list):
        tags = [str(t).lower().strip() for t in raw_tags if t]

    return {
        "title": title,
        "description": description,
        "event_type": "meetup",  # Luma is mostly meetups; categorize.py will refine
        "scope": scope,
        "mode": mode,
        "city": city,
        "venue": venue,
        "start_date": start_at,
        "end_date": end_at,
        "organizer": organizer,
        "registration_url": url,
        "source_name": SOURCE_NAME,
        "source_event_id": str(event_id),
        "tags": tags,
        "is_free": is_free,
        "is_student_friendly": False,
    }


# ─── Strategy 1: Discover API ─────────────────────────────────────────────────

def _fetch_discover(query: str) -> list[dict[str, Any]]:
    """Fetch events from Luma's discover/get-paginated-events API."""
    scope = _scope_for_query(query)
    params = {"query": query, "pagination_limit": 50}
    kind, data = fetch(
        DISCOVER_API,
        params=params,
        headers=_LUMA_HEADERS,
        want="json",
    )
    if kind == "error":
        logger.warning("Luma discover API error for query='%s': %s", query, data)
        return []

    if not isinstance(data, dict):
        logger.warning("Luma discover unexpected JSON type for query='%s': %s", query, type(data))
        return []

    # Response structure varies: try common keys
    entries = (
        data.get("entries")
        or data.get("events")
        or data.get("data", {}).get("entries")
        or data.get("data", {}).get("events")
        or []
    )
    if not isinstance(entries, list):
        logger.warning("Luma discover: could not find events list for query='%s'", query)
        return []

    results: list[dict[str, Any]] = []
    for raw in entries:
        if not isinstance(raw, dict):
            continue
        ev = _extract_event(raw, scope)
        if ev:
            results.append(ev)

    logger.info("Luma discover query='%s': %d events", query, len(results))
    return results


# ─── Strategy 2: Embedded __NEXT_DATA__ ───────────────────────────────────────

def _walk_next_data(obj: Any, found: list[dict]) -> None:
    """Recursively walk a parsed JSON object looking for event-like dicts."""
    if isinstance(obj, dict):
        # A dict looks like an event if it has a "name"/"title" and a "url"/"slug"
        has_event_keys = (
            ("name" in obj or "title" in obj)
            and ("url" in obj or "slug" in obj or "api_id" in obj)
        )
        if has_event_keys:
            found.append(obj)
        for v in obj.values():
            _walk_next_data(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _walk_next_data(item, found)


def _fetch_slug_page(slug: str) -> list[dict[str, Any]]:
    """Fetch https://lu.ma/<slug>, parse __NEXT_DATA__, extract events."""
    url = f"https://lu.ma/{slug}"
    scope = _scope_for_slug(slug)

    kind, data = fetch(url, want="html")
    if kind == "error":
        if "404" in str(data):
            logger.debug("Luma slug '%s' not found (404) — skipping", slug)
        else:
            logger.warning("Luma slug '%s' fetch error: %s", slug, data)
        return []

    # data is a BeautifulSoup object
    script_tag = data.find("script", {"id": "__NEXT_DATA__", "type": "application/json"})
    if not script_tag:
        logger.warning("Luma slug '%s': no __NEXT_DATA__ script tag found", slug)
        return []

    try:
        next_data = json.loads(script_tag.string or "{}")
    except json.JSONDecodeError as exc:
        logger.warning("Luma slug '%s': __NEXT_DATA__ JSON parse error: %s", slug, exc)
        return []

    raw_events: list[dict] = []
    _walk_next_data(next_data, raw_events)

    # De-dupe raw events by api_id within this page
    seen_ids: set[str] = set()
    results: list[dict[str, Any]] = []
    for raw in raw_events:
        ev = _extract_event(raw, scope)
        if not ev:
            continue
        eid = ev["source_event_id"]
        if eid in seen_ids:
            continue
        seen_ids.add(eid)
        results.append(ev)

    logger.info("Luma slug '%s': %d events extracted from __NEXT_DATA__", slug, len(results))
    return results


# ─── main entry point ─────────────────────────────────────────────────────────

def scrape() -> list[dict[str, Any]]:
    """Run both Luma strategies and return merged, de-duped event list."""
    all_events: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def _add(events: list[dict[str, Any]]) -> None:
        for ev in events:
            eid = ev.get("source_event_id", "")
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                all_events.append(ev)

    # ── Strategy 1: Discover API ──
    for query in DISCOVER_QUERIES:
        try:
            _add(_fetch_discover(query))
        except Exception as exc:
            logger.warning("Luma discover: unhandled exception for query='%s': %s", query, exc)
        time.sleep(config.HTTP_PAGE_WAIT)

    # ── Strategy 2: Page slugs ──
    for slug in PAGE_SLUGS:
        try:
            _add(_fetch_slug_page(slug))
        except Exception as exc:
            logger.warning("Luma slug '%s': unhandled exception: %s", slug, exc)
        time.sleep(config.HTTP_PAGE_WAIT)

    logger.info("Luma total (merged, deduped by id): %d events", len(all_events))
    return all_events
