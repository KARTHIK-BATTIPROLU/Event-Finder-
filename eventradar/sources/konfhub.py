"""
sources/konfhub.py — KonfHub Hyderabad tech conference & event explorer.

Scrapes https://konfhub.com/explore?location=Hyderabad
scope = india, city = hyderabad
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "konfhub"
PAGE_URL = "https://konfhub.com/explore"
BASE_URL = "https://konfhub.com"


def _clean(tag) -> str:
    return tag.get_text(separator=" ", strip=True) if tag else ""


def scrape() -> list[dict[str, Any]]:
    kind, soup = fetch(PAGE_URL, params={"location": "Hyderabad"}, want="html")
    if kind == "error":
        logger.warning("KonfHub scrape error: %s", soup)
        return []

    results: list[dict] = []

    # Try Next.js __NEXT_DATA__ first
    script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if script_tag:
        try:
            nd = json.loads(script_tag.string or "{}")
            props = nd.get("props", {}).get("pageProps", {})
            events_list = (
                props.get("events")
                or props.get("data", {}).get("events")
                or props.get("eventList")
                or []
            )
            for ev in events_list:
                if not isinstance(ev, dict):
                    continue
                title = str(ev.get("title") or ev.get("name") or "").strip()
                if not title:
                    continue
                slug = ev.get("slug") or str(ev.get("id") or "")
                url = f"{BASE_URL}/{slug}" if slug else ev.get("url") or ""
                if not url.startswith("http"):
                    url = BASE_URL + url
                if not url:
                    continue

                location_type = str(ev.get("event_type") or "").lower()
                if "online" in location_type:
                    mode = "online"
                elif "offline" in location_type:
                    mode = "offline"
                else:
                    mode = None

                results.append({
                    "title": title,
                    "description": str(ev.get("description") or "")[:300],
                    "event_type": "conference",
                    "scope": "india",
                    "mode": mode,
                    "city": "hyderabad",
                    "venue": str(ev.get("venue") or ev.get("location") or "").strip() or None,
                    "start_date": ev.get("start_date") or ev.get("starts_at"),
                    "end_date": ev.get("end_date") or ev.get("ends_at"),
                    "registration_deadline": ev.get("reg_deadline"),
                    "prize_pool": None,
                    "organizer": str(ev.get("organizer") or ev.get("organiser") or "").strip() or None,
                    "registration_url": url,
                    "source_name": SOURCE_NAME,
                    "source_event_id": str(ev.get("id") or slug),
                    "tags": [],
                    "is_student_friendly": False,
                    "is_free": None,
                })
            if results:
                logger.info("KonfHub (NEXT_DATA): %d events", len(results))
                return results
        except Exception as exc:
            logger.debug("KonfHub NEXT_DATA parse failed: %s", exc)

    # Fallback: HTML card scraping
    cards = (
        soup.find_all("div", class_=re.compile(r"card|event|conf", re.I))
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

        slug = href.rstrip("/").split("/")[-1]

        results.append({
            "title": title,
            "event_type": "conference",
            "scope": "india",
            "city": "hyderabad",
            "start_date": date_text or None,
            "registration_url": href,
            "source_name": SOURCE_NAME,
            "source_event_id": slug or href,
            "tags": [],
            "is_student_friendly": False,
            "is_free": None,
        })

    logger.info("KonfHub HTML: %d events", len(results))
    return results
