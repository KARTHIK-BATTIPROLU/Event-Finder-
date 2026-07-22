"""
sources/luma_api.py — Luma Plus API (KEY-GATED).

Requires: LUMA_API_KEY env var.
If absent, logs "skipped: no key" and returns [].

GET https://public-api.lu.ma/public/v1/calendar/list-events
    header x-luma-api-key: {LUMA_API_KEY}
Paginates on has_more.
"""
from __future__ import annotations

import logging
from typing import Any

from eventradar import config
from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "luma_api"
API_URL = "https://public-api.lu.ma/public/v1/calendar/list-events"


def _parse_data(data: Any) -> list[dict]:
    results: list[dict] = []
    entries = []

    if isinstance(data, dict):
        entries = data.get("entries") or data.get("events") or []
    elif isinstance(data, list):
        entries = data

    for raw in entries:
        if not isinstance(raw, dict):
            continue
        ev = raw.get("event") or raw

        title = str(ev.get("name") or ev.get("title") or "").strip()
        if not title:
            continue

        url = ev.get("url") or ""
        slug = ev.get("slug") or ev.get("api_id") or ""
        if not url and slug:
            url = f"https://lu.ma/{slug}"
        if not url:
            continue

        geo = ev.get("geo_address_info") or {}
        city_name = str(geo.get("city") or "").lower()
        city = None
        scope = "global"
        if "hyderabad" in city_name:
            city = "hyderabad"
            scope = "hyderabad"
        elif "bangalore" in city_name or "bengaluru" in city_name:
            city = "bangalore"
            scope = "india"
        elif "india" in city_name or city_name in ("mumbai", "delhi", "chennai", "pune"):
            scope = "india"

        results.append({
            "title": title,
            "description": str(ev.get("description") or "")[:300],
            "event_type": "meetup",
            "scope": scope,
            "mode": "online" if "online" in str(ev.get("location_type") or "").lower() else None,
            "city": city,
            "venue": str(geo.get("full_address") or "").strip() or None,
            "start_date": ev.get("start_at"),
            "end_date": ev.get("end_at"),
            "registration_deadline": None,
            "prize_pool": None,
            "organizer": None,
            "registration_url": url,
            "source_name": SOURCE_NAME,
            "source_event_id": str(ev.get("api_id") or ev.get("id") or slug),
            "tags": [],
            "is_student_friendly": False,
            "is_free": None,
        })

    return results


def scrape() -> list[dict[str, Any]]:
    if not config.LUMA_API_KEY:
        logger.info("Luma API: skipped: no key (LUMA_API_KEY not set)")
        return []

    headers = {"x-luma-api-key": config.LUMA_API_KEY}
    all_results: list[dict] = []
    cursor = None

    for _ in range(10):  # max 10 pages
        params: dict[str, Any] = {"limit": 50}
        if cursor:
            params["after"] = cursor

        kind, data = fetch(API_URL, params=params, headers=headers, want="json")
        if kind == "error":
            logger.warning("Luma API error: %s", data)
            break

        batch = _parse_data(data)
        all_results.extend(batch)

        if not isinstance(data, dict):
            break
        if not data.get("has_more"):
            break
        next_cursor = data.get("next_cursor") or (
            data.get("entries", [{}])[-1].get("event", {}).get("api_id")
            if data.get("entries") else None
        )
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor

    logger.info("Luma API: %d events", len(all_results))
    return all_results
