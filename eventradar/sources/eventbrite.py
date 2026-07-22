"""
sources/eventbrite.py — Eventbrite Hyderabad tech events (KEY-GATED).

Requires: EVENTBRITE_TOKEN env var.
If absent, logs "skipped: no key" and returns [].

GET https://www.eventbriteapi.com/v3/events/search/
    ?location.address=Hyderabad,India
    &location.within=50km
    &q=technology
    &expand=venue,organizer
    &categories=102          # Technology
"""
from __future__ import annotations

import logging
from typing import Any

from eventradar import config
from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "eventbrite"
API_URL = "https://www.eventbriteapi.com/v3/events/search/"


def _parse_data(data: Any) -> list[dict]:
    results: list[dict] = []
    events = []

    if isinstance(data, dict):
        events = data.get("events") or []

    for ev in events:
        if not isinstance(ev, dict):
            continue

        title = str(ev.get("name", {}).get("text") or "").strip()
        if not title:
            continue

        url = ev.get("url") or ev.get("resource_uri") or ""
        if not url:
            continue

        desc = (ev.get("description") or {}).get("text") or (ev.get("summary") or "")
        venue_obj = ev.get("venue") or {}
        addr = venue_obj.get("address") or {}
        city_name = str(addr.get("city") or "").lower()
        city = "hyderabad" if "hyderabad" in city_name else None
        venue = addr.get("localized_address_display") or addr.get("address_1") or None

        organizer_obj = ev.get("organizer") or {}
        organizer = str(organizer_obj.get("name") or "").strip() or None

        is_free = ev.get("is_free")

        results.append({
            "title": title,
            "description": str(desc)[:300],
            "event_type": "meetup",
            "scope": "india",
            "mode": "online" if ev.get("online_event") else "offline",
            "city": city or "hyderabad",
            "venue": venue,
            "start_date": ev.get("start", {}).get("utc"),
            "end_date": ev.get("end", {}).get("utc"),
            "registration_deadline": None,
            "prize_pool": None,
            "organizer": organizer,
            "registration_url": url,
            "source_name": SOURCE_NAME,
            "source_event_id": str(ev.get("id") or url.split("/")[-2]),
            "tags": [],
            "is_student_friendly": False,
            "is_free": is_free,
        })

    return results


def scrape() -> list[dict[str, Any]]:
    if not config.EVENTBRITE_TOKEN:
        logger.info("Eventbrite: skipped: no key (EVENTBRITE_TOKEN not set)")
        return []

    headers = {"Authorization": f"Bearer {config.EVENTBRITE_TOKEN}"}
    all_results: list[dict] = []

    page = 1
    while True:
        kind, data = fetch(
            API_URL,
            params={
                "location.address": "Hyderabad,India",
                "location.within": "50km",
                "q": "technology hackathon startup",
                "expand": "venue,organizer",
                "categories": "102",
                "page": page,
                "page_size": 50,
            },
            headers=headers,
            want="json",
        )
        if kind == "error":
            logger.warning("Eventbrite API error (page %d): %s", page, data)
            break

        batch = _parse_data(data)
        all_results.extend(batch)

        pagination = data.get("pagination") or {} if isinstance(data, dict) else {}
        if not pagination.get("has_more_items"):
            break
        page += 1
        if page > 5:  # safety cap
            break

    logger.info("Eventbrite: %d events", len(all_results))
    return all_results
