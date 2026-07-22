"""
sources/gdg_hyderabad.py — Google Developer Groups Hyderabad chapter events.

Scrapes https://gdg.community.dev/gdg-hyderabad/
scope = india, city = hyderabad
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "gdg_hyderabad"
PAGE_URL = "https://gdg.community.dev/gdg-hyderabad/"
BASE_URL = "https://gdg.community.dev"

# Also try the Bevy API (GDG uses Bevy platform)
BEVY_API = "https://gdg.community.dev/api/event/?chapter=1350&status=Upcoming&format=json"


def _clean(tag) -> str:
    return tag.get_text(separator=" ", strip=True) if tag else ""


def _parse_bevy_api(data: Any) -> list[dict]:
    results: list[dict] = []
    if isinstance(data, dict):
        events = data.get("results") or data.get("events") or []
    elif isinstance(data, list):
        events = data
    else:
        return []

    for ev in events:
        if not isinstance(ev, dict):
            continue
        title = str(ev.get("title") or ev.get("name") or "").strip()
        if not title:
            continue
        url = ev.get("url") or ev.get("event_url") or str(ev.get("id") or "")
        if url and not url.startswith("http"):
            url = BASE_URL + url
        if not url:
            continue

        results.append({
            "title": title,
            "description": str(ev.get("description_short") or ev.get("description") or "")[:300],
            "event_type": "meetup",
            "scope": "india",
            "mode": "offline" if not ev.get("is_online") else "online",
            "city": "hyderabad",
            "venue": str(ev.get("venue") or ev.get("location") or "").strip() or None,
            "start_date": ev.get("start_date") or ev.get("starts_at"),
            "end_date": ev.get("end_date"),
            "registration_deadline": ev.get("registration_close_date"),
            "prize_pool": None,
            "organizer": "GDG Hyderabad",
            "registration_url": url,
            "source_name": SOURCE_NAME,
            "source_event_id": str(ev.get("id") or url.split("/")[-1]),
            "tags": ["google"],
            "is_student_friendly": True,
            "is_free": True,
        })
    return results


def scrape() -> list[dict[str, Any]]:
    # Try Bevy API first
    kind, data = fetch(BEVY_API, want="json")
    if kind == "json":
        results = _parse_bevy_api(data)
        if results:
            logger.info("GDG Hyderabad (Bevy API): %d events", len(results))
            return results

    # Fall back to HTML scrape
    kind, soup = fetch(PAGE_URL, want="html")
    if kind == "error":
        logger.warning("GDG Hyderabad HTML scrape error: %s", soup)
        return []

    results: list[dict] = []

    # Try __NEXT_DATA__ or similar embedded data
    script_tag = soup.find("script", {"id": "__NEXT_DATA__"}) or soup.find(
        "script", string=re.compile(r"window\.__initial_state__")
    )

    if script_tag:
        try:
            raw = script_tag.string or ""
            if "window.__initial_state__" in raw:
                raw = raw.split("=", 1)[1].strip().rstrip(";")
            nd = json.loads(raw)
            props = nd.get("props", {}).get("pageProps", {})
            events_list = props.get("events") or []
            for ev in events_list:
                if not isinstance(ev, dict):
                    continue
                title = str(ev.get("title") or "").strip()
                if not title:
                    continue
                url = ev.get("url") or ""
                if url and not url.startswith("http"):
                    url = BASE_URL + url
                if not url:
                    continue
                results.append({
                    "title": title,
                    "description": str(ev.get("description_short") or "")[:300],
                    "event_type": "meetup",
                    "scope": "india",
                    "mode": None,
                    "city": "hyderabad",
                    "start_date": ev.get("start_date"),
                    "organizer": "GDG Hyderabad",
                    "registration_url": url,
                    "source_name": SOURCE_NAME,
                    "source_event_id": str(ev.get("id") or url.split("/")[-1]),
                    "tags": ["google"],
                    "is_student_friendly": True,
                    "is_free": True,
                })
            if results:
                logger.info("GDG Hyderabad (embedded data): %d events", len(results))
                return results
        except Exception as exc:
            logger.debug("GDG embedded data parse failed: %s", exc)

    # Final fallback: link scraping
    event_links = soup.find_all("a", href=re.compile(r"/events/|/e/", re.I))
    seen: set[str] = set()
    for link in event_links[:60]:
        href = link.get("href", "")
        if not href.startswith("http"):
            href = BASE_URL + href
        if href in seen:
            continue
        seen.add(href)
        title = _clean(link)
        if not title or len(title) < 3:
            continue
        slug = href.rstrip("/").split("/")[-1]
        results.append({
            "title": title,
            "event_type": "meetup",
            "scope": "india",
            "city": "hyderabad",
            "organizer": "GDG Hyderabad",
            "registration_url": href,
            "source_name": SOURCE_NAME,
            "source_event_id": slug or href,
            "tags": ["google"],
            "is_student_friendly": True,
            "is_free": True,
        })

    logger.info("GDG Hyderabad (HTML links): %d events", len(results))
    return results
