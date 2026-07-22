"""
sources/unstop.py — Unstop hackathon scraper (India focus).

GET https://unstop.com/api/public/opportunity/search-result
    ?opportunity=hackathons&oppstatus=open&per_page=30
scope = india
"""
from __future__ import annotations

import logging
from typing import Any

from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "unstop"
API_URL = "https://unstop.com/api/public/opportunity/search-result"


def _parse_data(data: Any) -> list[dict]:
    results: list[dict] = []
    items = []

    if isinstance(data, dict):
        inner = data.get("data") or {}
        if isinstance(inner, dict):
            items = inner.get("data") or inner.get("items") or []
        elif isinstance(inner, list):
            items = inner

    for item in items:
        if not isinstance(item, dict):
            continue

        title = str(item.get("title") or item.get("name") or "").strip()
        if not title:
            continue

        slug = item.get("seo_url") or item.get("slug") or str(item.get("id", ""))
        url = f"https://unstop.com/{slug}" if slug else ""
        if not url.startswith("http"):
            continue

        org = item.get("organisation") or {}
        organizer = str(org.get("name") if isinstance(org, dict) else org or "").strip() or None

        prizes = item.get("prizes") or []
        prize_pool = None
        if isinstance(prizes, list) and prizes:
            p0 = prizes[0]
            if isinstance(p0, dict):
                cash = p0.get("cash") or p0.get("amount")
                curr = str(p0.get("currency") or "").lower()
                curr_sym = "₹" if "rupee" in curr or "inr" in curr or not curr else "$"
                if cash:
                    try:
                        prize_pool = f"{curr_sym}{int(float(cash)):,}"
                    except (ValueError, TypeError):
                        prize_pool = f"{curr_sym}{cash}"
                elif p0.get("others"):
                    prize_pool = str(p0["others"])[:100]
            elif isinstance(p0, (str, int, float)):
                prize_pool = str(p0)

        # Mode detection
        location = str(item.get("type") or item.get("location_type") or "").lower()
        if "online" in location or "virtual" in location:
            mode = "online"
        elif "offline" in location or "in-person" in location:
            mode = "offline"
        else:
            mode = None

        results.append({
            "title": title,
            "description": str(item.get("description_text") or item.get("about") or "")[:300],
            "event_type": "hackathon",
            "scope": "india",
            "mode": mode,
            "city": None,
            "venue": str(item.get("venue") or "").strip() or None,
            "start_date": item.get("start_date") or item.get("starts_at"),
            "end_date": item.get("end_date") or item.get("ends_at"),
            "registration_deadline": item.get("reg_last_date") or item.get("apply_by"),
            "prize_pool": prize_pool,
            "organizer": organizer,
            "registration_url": url,
            "source_name": SOURCE_NAME,
            "source_event_id": str(item.get("id") or slug),
            "tags": [],
            "is_student_friendly": True,
            "is_free": True,
        })

    return results


def scrape() -> list[dict[str, Any]]:
    kind, data = fetch(
        API_URL,
        params={
            "opportunity": "hackathons",
            "oppstatus": "open",
            "per_page": 30,
        },
        want="json",
    )
    if kind == "error":
        logger.warning("Unstop API error: %s", data)
        return []

    results = _parse_data(data)
    logger.info("Unstop: %d events", len(results))
    return results
