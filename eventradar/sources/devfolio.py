"""
sources/devfolio.py — Devfolio hackathon scraper.

Primary: GET https://devfolio.co/api/hackathons?filter=upcoming
Fallback: HTML scrape of https://devfolio.co/hackathons
scope = global
"""
from __future__ import annotations

import logging
from typing import Any

from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "devfolio"
API_URL = "https://devfolio.co/api/hackathons"
PAGE_URL = "https://devfolio.co/hackathons"


def _parse_api(data: Any) -> list[dict]:
    """Parse the Devfolio API JSON response."""
    results: list[dict] = []
    hackathons = []

    if isinstance(data, list):
        hackathons = data
    elif isinstance(data, dict):
        hackathons = (
            data.get("results")
            or data.get("hackathons")
            or data.get("data")
            or []
        )

    for h in hackathons:
        if not isinstance(h, dict):
            continue

        title = str(h.get("name") or h.get("title") or "").strip()
        if not title:
            continue

        slug = h.get("slug") or ""
        url = f"https://devfolio.co/{slug}" if slug else h.get("url") or ""
        if not url:
            continue

        prizes = h.get("prizes") or {}
        prize_pool = None
        if isinstance(prizes, dict):
            prize_pool = prizes.get("prize_pool") or prizes.get("total")
        elif isinstance(prizes, (int, float)):
            prize_pool = str(prizes)

        results.append({
            "title": title,
            "description": str(h.get("tagline") or h.get("description") or "")[:300],
            "event_type": "hackathon",
            "scope": "global",
            "mode": "online" if h.get("is_online") else ("offline" if h.get("venue") else None),
            "city": None,
            "venue": str(h.get("venue") or "").strip() or None,
            "start_date": h.get("starts_at") or h.get("start_date"),
            "end_date": h.get("ends_at") or h.get("end_date"),
            "registration_deadline": h.get("registration_deadline") or h.get("apply_by"),
            "prize_pool": str(prize_pool) if prize_pool else None,
            "organizer": str(h.get("organization_name") or "").strip() or None,
            "registration_url": url,
            "source_name": SOURCE_NAME,
            "source_event_id": str(h.get("id") or slug),
            "tags": [],
            "is_student_friendly": True,  # Devfolio is student-focused
            "is_free": True,
        })

    return results


def _scrape_html() -> list[dict]:
    """Fallback: parse the HTML hackathon listing page."""
    kind, data = fetch(PAGE_URL, want="html")
    if kind == "error":
        logger.warning("Devfolio HTML fallback error: %s", data)
        return []

    results: list[dict] = []
    cards = data.find_all("div", class_=lambda c: c and "hackathon" in c.lower())
    if not cards:
        # Try generic card selectors
        cards = data.find_all("a", href=lambda h: h and "/hackathons/" in h)

    for card in cards[:50]:
        link = card if card.name == "a" else card.find("a")
        if not link:
            continue
        href = link.get("href", "")
        if not href.startswith("http"):
            href = "https://devfolio.co" + href
        title_tag = card.find(["h2", "h3", "h4"]) or card
        title = title_tag.get_text(strip=True)
        if not title or len(title) < 3:
            continue
        results.append({
            "title": title,
            "event_type": "hackathon",
            "scope": "global",
            "registration_url": href,
            "source_name": SOURCE_NAME,
            "source_event_id": href.split("/")[-1] or href,
            "tags": [],
            "is_student_friendly": True,
        })

    return results


def scrape() -> list[dict[str, Any]]:
    # Try API first
    kind, data = fetch(API_URL, params={"filter": "upcoming"}, want="json")
    if kind == "json":
        results = _parse_api(data)
        if results:
            logger.info("Devfolio API: %d events", len(results))
            return results

    logger.info("Devfolio API failed or empty, trying HTML fallback")
    results = _scrape_html()
    logger.info("Devfolio HTML fallback: %d events", len(results))
    return results
