"""
sources/devevents.py — dev.events India hackathon listing.

Scrapes https://dev.events/hackathons/AS/IN (AS = Asia, IN = India)
scope = india
"""
from __future__ import annotations

import logging
import re
from typing import Any

from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "devevents"
PAGE_URL = "https://dev.events/hackathons/AS/IN"


def _clean(tag) -> str:
    return tag.get_text(separator=" ", strip=True) if tag else ""


def scrape() -> list[dict[str, Any]]:
    kind, soup = fetch(PAGE_URL, want="html")
    if kind == "error":
        logger.warning("DevEvents scrape error: %s", soup)
        return []

    results: list[dict] = []

    # dev.events uses article or div cards with event data
    cards = soup.find_all("article") or soup.find_all("div", class_=re.compile(r"event|card", re.I))

    for card in cards[:60]:
        link_tag = card.find("a", href=True)
        if not link_tag:
            continue

        href = link_tag["href"]
        if not href.startswith("http"):
            href = "https://dev.events" + href

        title_tag = card.find(["h2", "h3", "h4"]) or link_tag
        title = _clean(title_tag)
        if not title or len(title) < 3:
            continue

        date_tag = card.find("time") or card.find(class_=re.compile(r"date", re.I))
        date_text = _clean(date_tag)
        if hasattr(date_tag, "get"):
            date_text = date_tag.get("datetime", "") or date_text

        loc_tag = card.find(class_=re.compile(r"location|venue|city|place", re.I))
        location = _clean(loc_tag)

        mode = "online" if "online" in location.lower() or "virtual" in location.lower() else None

        slug = href.rstrip("/").split("/")[-1]

        results.append({
            "title": title,
            "description": None,
            "event_type": "hackathon",
            "scope": "india",
            "mode": mode,
            "city": None,
            "venue": location or None,
            "start_date": date_text or None,
            "registration_deadline": None,
            "prize_pool": None,
            "organizer": None,
            "registration_url": href,
            "source_name": SOURCE_NAME,
            "source_event_id": slug or href,
            "tags": [],
            "is_student_friendly": True,
            "is_free": None,
        })

    logger.info("DevEvents: %d events", len(results))
    return results
