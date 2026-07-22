"""
sources/reskilll.py — Reskilll all-hacks listing.

Scrapes https://reskilll.com/allhacks
scope = india
"""
from __future__ import annotations

import logging
import re
from typing import Any

from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "reskilll"
PAGE_URL = "https://reskilll.com/allhacks"
BASE_URL = "https://reskilll.com"


def _clean(tag) -> str:
    return tag.get_text(separator=" ", strip=True) if tag else ""


def scrape() -> list[dict[str, Any]]:
    kind, soup = fetch(PAGE_URL, want="html")
    if kind == "error":
        logger.warning("Reskilll scrape error: %s", soup)
        return []

    results: list[dict] = []

    # Reskilll typically has cards with class containing 'hack' or 'event'
    cards = (
        soup.find_all("div", class_=re.compile(r"card|hack|event", re.I))
        or soup.find_all("article")
    )

    for card in cards[:60]:
        link_tag = card.find("a", href=True)
        if not link_tag:
            continue

        href = link_tag["href"]
        if not href.startswith("http"):
            href = BASE_URL + href

        title_tag = card.find(["h2", "h3", "h4"]) or link_tag
        title = _clean(title_tag)
        if not title or len(title) < 3:
            continue

        date_tag = card.find(class_=re.compile(r"date|time", re.I)) or card.find("time")
        date_text = _clean(date_tag)

        prize_tag = card.find(class_=re.compile(r"prize|reward|amount", re.I))
        prize = _clean(prize_tag) or None

        slug = href.rstrip("/").split("/")[-1]

        results.append({
            "title": title,
            "description": None,
            "event_type": "hackathon",
            "scope": "india",
            "mode": "online",
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

    logger.info("Reskilll: %d events", len(results))
    return results
