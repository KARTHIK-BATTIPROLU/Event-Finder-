"""
sources/hack2skill.py — Hack2Skill event explorer.

Scrapes https://hack2skill.com/explore
scope = global
"""
from __future__ import annotations

import logging
import re
from typing import Any

from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "hack2skill"
PAGE_URL = "https://hack2skill.com/explore"
BASE_URL = "https://hack2skill.com"


def _clean(tag) -> str:
    return tag.get_text(separator=" ", strip=True) if tag else ""


def scrape() -> list[dict[str, Any]]:
    kind, soup = fetch(PAGE_URL, want="html")
    if kind == "error":
        logger.warning("Hack2Skill scrape error: %s", soup)
        return []

    results: list[dict] = []

    cards = (
        soup.find_all("div", class_=re.compile(r"card|event|hack", re.I))
        or soup.find_all("article")
        or soup.find_all("li", class_=re.compile(r"event|hack", re.I))
    )

    for card in cards[:60]:
        link_tag = card.find("a", href=True)
        if not link_tag:
            continue

        href = link_tag["href"]
        if not href.startswith("http"):
            href = BASE_URL + href

        # Skip navigation/promo links
        if href in (BASE_URL, BASE_URL + "/", PAGE_URL):
            continue

        title_tag = card.find(["h2", "h3", "h4"]) or link_tag
        title = _clean(title_tag)
        if not title or len(title) < 3:
            continue

        date_tag = card.find(class_=re.compile(r"date|deadline", re.I)) or card.find("time")
        date_text = _clean(date_tag)

        prize_tag = card.find(class_=re.compile(r"prize|reward|worth", re.I))
        prize = _clean(prize_tag) or None

        slug = href.rstrip("/").split("/")[-1]

        results.append({
            "title": title,
            "description": None,
            "event_type": "hackathon",
            "scope": "global",
            "mode": None,
            "city": None,
            "venue": None,
            "start_date": date_text or None,
            "registration_deadline": None,
            "prize_pool": prize,
            "organizer": None,
            "registration_url": href,
            "source_name": SOURCE_NAME,
            "source_event_id": slug or href,
            "tags": [],
            "is_student_friendly": True,
            "is_free": True,
        })

    logger.info("Hack2Skill: %d events", len(results))
    return results
