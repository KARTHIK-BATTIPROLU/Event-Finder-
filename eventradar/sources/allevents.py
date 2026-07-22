"""
sources/allevents.py — AllEvents.in Hyderabad Technology category.

Scrapes https://allevents.in/hyderabad/technology
scope = india, city = hyderabad
"""
from __future__ import annotations

import logging
import re
from typing import Any

from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "allevents"
PAGE_URL = "https://allevents.in/hyderabad/technology"
BASE_URL = "https://allevents.in"


def _clean(tag) -> str:
    return tag.get_text(separator=" ", strip=True) if tag else ""


def scrape() -> list[dict[str, Any]]:
    kind, soup = fetch(PAGE_URL, want="html")
    if kind == "error":
        logger.warning("AllEvents scrape error: %s", soup)
        return []

    results: list[dict] = []

    # AllEvents uses li.event-item or div.event-item
    cards = (
        soup.find_all("li", class_=re.compile(r"event", re.I))
        or soup.find_all("div", class_=re.compile(r"event-item|event-card", re.I))
        or soup.find_all("article")
    )

    for card in cards[:60]:
        link_tag = card.find("a", href=re.compile(r"allevents\.in|/e/", re.I))
        if not link_tag:
            link_tag = card.find("a", href=True)
        if not link_tag:
            continue

        href = link_tag["href"]
        if not href.startswith("http"):
            href = BASE_URL + href

        title_tag = (
            card.find(class_=re.compile(r"title|name|event-name", re.I))
            or card.find(["h2", "h3", "h4"])
            or link_tag
        )
        title = _clean(title_tag)
        if not title or len(title) < 3:
            continue

        # Date
        date_tag = card.find(class_=re.compile(r"date|time|when", re.I)) or card.find("time")
        date_text = _clean(date_tag)

        # Venue
        venue_tag = card.find(class_=re.compile(r"venue|location|place", re.I))
        venue = _clean(venue_tag) or None

        slug = href.rstrip("/").split("/")[-1]

        results.append({
            "title": title,
            "description": None,
            "event_type": "meetup",
            "scope": "india",
            "mode": None,
            "city": "hyderabad",
            "venue": venue,
            "start_date": date_text or None,
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

    logger.info("AllEvents: %d events", len(results))
    return results
