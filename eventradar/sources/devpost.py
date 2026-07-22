"""
sources/devpost.py — Devpost hackathon scraper.

GET https://devpost.com/api/hackathons?status[]=upcoming&page=1
scope = global
"""
from __future__ import annotations

import logging
import time
from typing import Any

from eventradar import config
from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "devpost"
API_URL = "https://devpost.com/api/hackathons"
MAX_PAGES = 3


def _parse_hackathons(data: Any) -> list[dict]:
    results: list[dict] = []
    hackathons = []

    if isinstance(data, dict):
        hackathons = data.get("hackathons") or data.get("data") or []
    elif isinstance(data, list):
        hackathons = data

    for h in hackathons:
        if not isinstance(h, dict):
            continue

        title = str(h.get("title") or "").strip()
        if not title:
            continue

        url = h.get("url") or h.get("submission_gallery_url") or ""
        if not url:
            continue
        if not url.startswith("http"):
            url = "https://devpost.com" + url

        prizes_amount = h.get("prize_amount")
        prize_pool = None
        if prizes_amount:
            try:
                prize_pool = f"${int(float(prizes_amount)):,}"
            except (ValueError, TypeError):
                prize_pool = str(prizes_amount)

        themes: list[str] = []
        for theme in h.get("themes") or []:
            if isinstance(theme, dict) and theme.get("name"):
                themes.append(str(theme["name"]).lower())

        results.append({
            "title": title,
            "description": str(h.get("tagline") or "")[:300],
            "event_type": "hackathon",
            "scope": "global",
            "mode": "online" if h.get("open_state") == "open" else None,
            "start_date": h.get("submission_period_dates", "").split(" - ")[0] if h.get("submission_period_dates") else None,
            "end_date": h.get("submission_period_dates", "").split(" - ")[-1] if h.get("submission_period_dates") else None,
            "registration_deadline": h.get("registrations_count"),
            "prize_pool": prize_pool,
            "organizer": str(h.get("organization_name") or "").strip() or None,
            "registration_url": url,
            "source_name": SOURCE_NAME,
            "source_event_id": str(h.get("id") or url.split("/")[-1]),
            "tags": themes,
            "is_student_friendly": True,
            "is_free": True,
        })

    return results


def scrape() -> list[dict[str, Any]]:
    all_results: list[dict] = []

    for page in range(1, MAX_PAGES + 1):
        kind, data = fetch(
            API_URL,
            params={"status[]": "upcoming", "page": page},
            want="json",
            page_wait=config.HTTP_PAGE_WAIT if page > 1 else 0,
        )
        if kind == "error":
            logger.warning("Devpost API page %d error: %s", page, data)
            break
        batch = _parse_hackathons(data)
        if not batch:
            break
        all_results.extend(batch)
        # Check pagination
        if isinstance(data, dict):
            meta = data.get("meta") or {}
            total_count = meta.get("total_count", 0)
            if len(all_results) >= total_count:
                break

    logger.info("Devpost: %d events", len(all_results))
    return all_results
