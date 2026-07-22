"""
sources/hackerearth.py — HackerEarth events scraper.

GET https://www.hackerearth.com/chrome-extension/events/
scope = global
"""
from __future__ import annotations

import logging
from typing import Any

from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "hackerearth"
API_URL = "https://www.hackerearth.com/chrome-extension/events/"


def _parse_data(data: Any) -> list[dict]:
    results: list[dict] = []
    events = []

    if isinstance(data, list):
        events = data
    elif isinstance(data, dict):
        events = data.get("response") or data.get("events") or data.get("data") or []

    for ev in events:
        if not isinstance(ev, dict):
            continue

        title = str(ev.get("title") or ev.get("name") or "").strip()
        if not title:
            continue

        url = ev.get("url") or ev.get("event_url") or ""
        if not url:
            continue
        if not url.startswith("http"):
            url = "https://www.hackerearth.com" + url

        event_id = str(ev.get("id") or ev.get("event_id") or url.split("/")[-2] or url)

        # HackerEarth type field
        raw_type = str(ev.get("type") or "").lower()
        event_type = "hackathon" if "hack" in raw_type else "workshop"

        results.append({
            "title": title,
            "description": str(ev.get("description") or ev.get("tagline") or "")[:300],
            "event_type": event_type,
            "scope": "global",
            "mode": "online",  # HackerEarth is predominantly online
            "start_date": ev.get("start_utc_tz") or ev.get("start_time") or ev.get("start_date"),
            "end_date": ev.get("end_utc_tz") or ev.get("end_time") or ev.get("end_date"),
            "registration_deadline": ev.get("enrollment_end_time") or ev.get("reg_deadline"),
            "prize_pool": str(ev.get("prize_amount") or "").strip() or None,
            "organizer": str(ev.get("company_name") or ev.get("organizer") or "").strip() or None,
            "registration_url": url,
            "source_name": SOURCE_NAME,
            "source_event_id": event_id,
            "tags": [],
            "is_student_friendly": True,
            "is_free": True,
        })

    return results


def scrape() -> list[dict[str, Any]]:
    kind, data = fetch(API_URL, want="json")
    if kind == "error":
        logger.warning("HackerEarth API error: %s", data)
        return []

    results = _parse_data(data)
    logger.info("HackerEarth: %d events", len(results))
    return results
