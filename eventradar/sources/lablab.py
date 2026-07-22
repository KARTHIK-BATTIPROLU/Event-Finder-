"""
sources/lablab.py — LabLab.ai AI hackathons.

Scrapes https://lablab.ai/ai-hackathons
scope = global
"""
from __future__ import annotations

import logging
import re
from typing import Any

from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "lablab"
PAGE_URL = "https://lablab.ai/ai-hackathons"
BASE_URL = "https://lablab.ai"


def _clean(tag) -> str:
    return tag.get_text(separator=" ", strip=True) if tag else ""


def scrape() -> list[dict[str, Any]]:
    kind, soup = fetch(PAGE_URL, want="html")
    if kind == "error":
        logger.warning("LabLab scrape error: %s", soup)
        return []

    results: list[dict] = []

    # LabLab uses Next.js; try to find the __NEXT_DATA__ script first
    import json
    script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if script_tag:
        try:
            nd = json.loads(script_tag.string or "{}")
            # Walk to find hackathon list
            props = nd.get("props", {}).get("pageProps", {})
            events_list = (
                props.get("hackathons")
                or props.get("events")
                or props.get("data", {}).get("hackathons")
                or []
            )
            for ev in events_list:
                if not isinstance(ev, dict):
                    continue
                title = str(ev.get("title") or ev.get("name") or "").strip()
                if not title:
                    continue
                slug = ev.get("slug") or ev.get("id") or ""
                url = f"{BASE_URL}/event/{slug}" if slug else ev.get("url") or ""
                if not url:
                    continue
                results.append({
                    "title": title,
                    "description": str(ev.get("description") or "")[:300],
                    "event_type": "hackathon",
                    "scope": "global",
                    "mode": "online",
                    "start_date": ev.get("start_date") or ev.get("starts_at"),
                    "end_date": ev.get("end_date") or ev.get("ends_at"),
                    "registration_deadline": ev.get("application_deadline"),
                    "prize_pool": str(ev.get("prize_pool") or "").strip() or None,
                    "organizer": str(ev.get("organizer") or "LabLab.ai").strip(),
                    "registration_url": url,
                    "source_name": SOURCE_NAME,
                    "source_event_id": str(ev.get("id") or slug),
                    "tags": ["ai", "ml"],
                    "is_student_friendly": True,
                    "is_free": True,
                })
            if results:
                logger.info("LabLab (NEXT_DATA): %d events", len(results))
                return results
        except Exception as exc:
            logger.debug("LabLab NEXT_DATA parse failed: %s", exc)

    # Fallback: HTML card scraping
    cards = (
        soup.find_all("div", class_=re.compile(r"card|hackathon|event", re.I))
        or soup.find_all("article")
    )
    for card in cards[:60]:
        link_tag = card.find("a", href=True)
        if not link_tag:
            continue
        href = link_tag["href"]
        if not href.startswith("http"):
            href = BASE_URL + href
        if "/event/" not in href and "/ai-hackathons/" not in href:
            continue
        title_tag = card.find(["h2", "h3", "h4"]) or link_tag
        title = _clean(title_tag)
        if not title or len(title) < 3:
            continue
        slug = href.rstrip("/").split("/")[-1]
        results.append({
            "title": title,
            "event_type": "hackathon",
            "scope": "global",
            "mode": "online",
            "registration_url": href,
            "source_name": SOURCE_NAME,
            "source_event_id": slug or href,
            "tags": ["ai", "ml"],
            "is_student_friendly": True,
            "is_free": True,
        })

    logger.info("LabLab HTML: %d events", len(results))
    return results
