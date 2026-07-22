"""
sources/mlh.py — Major League Hacking season events.

Scrapes https://mlh.io/seasons/2026/events — HTML page with event cards.
scope = global
"""
from __future__ import annotations

import logging
import re
from typing import Any

from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "mlh"
PAGE_URL = "https://mlh.io/seasons/2026/events"


def _clean_text(tag) -> str:
    return tag.get_text(separator=" ", strip=True) if tag else ""


def scrape() -> list[dict[str, Any]]:
    kind, soup = fetch(PAGE_URL, want="html")
    if kind == "error":
        logger.warning("MLH scrape error: %s", soup)
        return []

    results: list[dict] = []

    # MLH uses <div class="event"> or similar
    event_containers = soup.find_all("div", class_=re.compile(r"event", re.I))
    if not event_containers:
        event_containers = soup.find_all("article")
    if not event_containers:
        # Try finding all links that look like hackathon events
        event_containers = soup.find_all("a", href=re.compile(r"mlh\.io|hackathon"))

    for container in event_containers[:100]:
        # Title
        title_tag = container.find(["h3", "h2", "h4"]) or container.find(class_=re.compile(r"title|name", re.I))
        title = _clean_text(title_tag)
        if not title or len(title) < 3:
            continue

        # URL
        link = container.find("a")
        url = ""
        if link:
            url = link.get("href", "")
        if not url:
            continue
        if not url.startswith("http"):
            url = "https://mlh.io" + url

        # Date
        date_tag = container.find(class_=re.compile(r"date|time", re.I)) or container.find("time")
        date_text = _clean_text(date_tag)

        # Location
        loc_tag = container.find(class_=re.compile(r"location|venue|city", re.I))
        location = _clean_text(loc_tag)
        mode = "online" if "online" in location.lower() or "virtual" in location.lower() else "offline"

        slug = url.split("/")[-1] or url.split("/")[-2]

        results.append({
            "title": title,
            "description": None,
            "event_type": "hackathon",
            "scope": "global",
            "mode": mode,
            "city": None,
            "venue": location or None,
            "start_date": date_text or None,
            "end_date": None,
            "registration_deadline": None,
            "prize_pool": None,
            "organizer": "MLH",
            "registration_url": url,
            "source_name": SOURCE_NAME,
            "source_event_id": slug,
            "tags": ["students"],
            "is_student_friendly": True,
            "is_free": True,
        })

    logger.info("MLH: %d events", len(results))
    return results
