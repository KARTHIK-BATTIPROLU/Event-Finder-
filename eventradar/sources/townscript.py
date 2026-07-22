"""
sources/townscript.py — Townscript Hyderabad technology events.

Scrapes https://www.townscript.com/browse-events/hyderabad--technology
scope = india, city = hyderabad
"""
from __future__ import annotations

import logging
import re
from typing import Any

from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "townscript"
PAGE_URL = "https://www.townscript.com/browse-events/hyderabad--technology"
BASE_URL = "https://www.townscript.com"


def _clean(tag) -> str:
    return tag.get_text(separator=" ", strip=True) if tag else ""


def scrape() -> list[dict[str, Any]]:
    kind, soup = fetch(PAGE_URL, want="html")
    if kind == "error":
        logger.warning("Townscript scrape error: %s", soup)
        return []

    results: list[dict] = []

    # Townscript typically uses div or li with event classes
    cards = (
        soup.find_all("div", class_=re.compile(r"event-card|event-item|listing", re.I))
        or soup.find_all("li", class_=re.compile(r"event", re.I))
        or soup.find_all("article")
    )

    if not cards:
        # Try all links to event pages
        cards = soup.find_all("a", href=re.compile(r"/e/|/event/", re.I))

    for card in cards[:60]:
        link_tag = card if card.name == "a" else card.find("a", href=True)
        if not link_tag:
            continue

        href = link_tag.get("href", "")
        if not href.startswith("http"):
            href = BASE_URL + href
        if not href or href == BASE_URL:
            continue

        title_tag = card.find(["h2", "h3", "h4"]) if card.name != "a" else card
        title = _clean(title_tag)
        if not title or len(title) < 3:
            continue

        date_tag = card.find(class_=re.compile(r"date|time|when", re.I)) if card.name != "a" else None
        date_text = _clean(date_tag) if date_tag else None

        venue_tag = card.find(class_=re.compile(r"venue|location", re.I)) if card.name != "a" else None
        venue = _clean(venue_tag) if venue_tag else None

        slug = href.rstrip("/").split("/")[-1]

        results.append({
            "title": title,
            "description": None,
            "event_type": "meetup",
            "scope": "india",
            "mode": None,
            "city": "hyderabad",
            "venue": venue,
            "start_date": date_text,
            "registration_deadline": None,
            "prize_pool": None,
            "organizer": None,
            "registration_url": href,
            "source_name": SOURCE_NAME,
            "source_event_id": slug or href,
            "tags": [],
            "is_student_friendly": False,
            "is_free": None,
        })

    logger.info("Townscript: %d events", len(results))
    return results
