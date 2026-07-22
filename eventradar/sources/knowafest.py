"""
sources/knowafest.py — KnowAFest Telangana/Hyderabad tech events.

Scrapes https://www.knowafest.com/explore/state/Telangana
scope = india, city = hyderabad
"""
from __future__ import annotations

import logging
import re
from typing import Any

from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "knowafest"
PAGE_URL = "https://www.knowafest.com/explore/state/Telangana"
BASE_URL = "https://www.knowafest.com"


def _clean(tag) -> str:
    return tag.get_text(separator=" ", strip=True) if tag else ""


def scrape() -> list[dict[str, Any]]:
    kind, soup = fetch(PAGE_URL, want="html")
    if kind == "error":
        logger.warning("KnowAFest scrape error: %s", soup)
        return []

    results: list[dict] = []

    # KnowAFest uses div.event-list or table rows
    cards = soup.find_all("div", class_=re.compile(r"event", re.I))
    if not cards:
        cards = soup.find_all("tr")

    for card in cards[:60]:
        link_tag = card.find("a", href=True)
        if not link_tag:
            continue

        href = link_tag["href"]
        if not href.startswith("http"):
            href = BASE_URL + href

        title = _clean(link_tag) or _clean(card.find(["h2", "h3", "h4"]))
        if not title or len(title) < 3:
            continue

        # Date
        date_tag = card.find(class_=re.compile(r"date|time", re.I)) or card.find("time")
        date_text = _clean(date_tag)

        # Mode
        mode_tag = card.find(class_=re.compile(r"mode|type|online|offline", re.I))
        mode_text = _clean(mode_tag).lower()
        if "online" in mode_text:
            mode = "online"
        elif "offline" in mode_text or "campus" in mode_text:
            mode = "offline"
        else:
            mode = None

        slug = href.rstrip("/").split("/")[-1]

        results.append({
            "title": title,
            "description": None,
            "event_type": "hackathon",
            "scope": "india",
            "mode": mode,
            "city": "hyderabad",
            "venue": None,
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

    logger.info("KnowAFest: %d events", len(results))
    return results
