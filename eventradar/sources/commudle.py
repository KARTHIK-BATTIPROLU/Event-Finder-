"""
sources/commudle.py — Commudle Hyderabad community events.

GET https://www.commudle.com/api/v2/events?city=Hyderabad
scope = india, city = hyderabad
"""
from __future__ import annotations

import logging
from typing import Any

from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "commudle"
API_URL = "https://www.commudle.com/api/v2/events"


def _parse_data(data: Any) -> list[dict]:
    results: list[dict] = []
    events = []

    if isinstance(data, list):
        events = data
    elif isinstance(data, dict):
        events = (
            data.get("events")
            or data.get("data")
            or data.get("results")
            or []
        )

    for ev in events:
        if not isinstance(ev, dict):
            continue

        title = str(ev.get("name") or ev.get("title") or "").strip()
        if not title:
            continue

        slug = ev.get("slug") or str(ev.get("id") or "")
        url = ev.get("url") or (f"https://www.commudle.com/events/{slug}" if slug else "")
        if not url:
            continue
        if not url.startswith("http"):
            url = "https://www.commudle.com" + url

        # Mode
        location_type = str(ev.get("location_type") or ev.get("event_type") or "").lower()
        if "online" in location_type or "virtual" in location_type:
            mode = "online"
        elif "offline" in location_type or "hybrid" in location_type:
            mode = "offline"
        else:
            mode = None

        results.append({
            "title": title,
            "description": str(ev.get("description") or ev.get("about") or "")[:300],
            "event_type": "meetup",
            "scope": "india",
            "mode": mode,
            "city": "hyderabad",
            "venue": str(ev.get("venue") or ev.get("location") or "").strip() or None,
            "start_date": ev.get("start_time") or ev.get("starts_at") or ev.get("start_date"),
            "end_date": ev.get("end_time") or ev.get("ends_at") or ev.get("end_date"),
            "registration_deadline": ev.get("registration_deadline"),
            "prize_pool": None,
            "organizer": str(ev.get("community_name") or ev.get("organizer") or "").strip() or None,
            "registration_url": url,
            "source_name": SOURCE_NAME,
            "source_event_id": str(ev.get("id") or slug),
            "tags": [],
            "is_student_friendly": False,
            "is_free": True,
        })

    return results


def scrape() -> list[dict[str, Any]]:
    kind, data = fetch(API_URL, params={"city": "Hyderabad"}, want="json")
    if kind == "error":
        logger.warning("Commudle API error: %s", data)
        return []

    results = _parse_data(data)
    logger.info("Commudle: %d events", len(results))
    return results
