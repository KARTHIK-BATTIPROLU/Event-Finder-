"""
sources/meetup.py — Meetup GraphQL API (KEY-GATED).

Requires: MEETUP_TOKEN env var.
If absent, logs "skipped: no key" and returns [].

POST https://api.meetup.com/gql
Searches for tech/hackathon/startup/founders events near Hyderabad and Bangalore.
"""
from __future__ import annotations

import logging
from typing import Any

from eventradar import config
from eventradar.http import fetch

logger = logging.getLogger(__name__)

SOURCE_NAME = "meetup"
GQL_URL = "https://api.meetup.com/gql"

_KEYWORDS = ["technology", "hackathon", "ai", "startup", "founders", "developer"]
_LOCATIONS = [
    {"name": "Hyderabad", "lat": 17.385, "lon": 78.4867, "scope": "hyderabad"},
    {"name": "Bangalore", "lat": 12.9716, "lon": 77.5946, "scope": "india"},
]

_GQL_QUERY = """
query SearchEvents($lat: Float!, $lon: Float!, $radius: Float!, $query: String!, $after: String) {
  keywordSearch(
    filter: {
      query: $query,
      lat: $lat,
      lon: $lon,
      radius: $radius,
      source: EVENTS,
      after: $after
    }
  ) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        result {
          ... on Event {
            id
            title
            description
            dateTime
            endTime
            eventUrl
            isOnline
            venue { name city lat lon address }
            group { name }
            feeSettings { amount currency }
          }
        }
      }
    }
  }
}
"""


def _parse_edges(edges: list, scope: str) -> list[dict]:
    results: list[dict] = []
    for edge in edges:
        node = edge.get("node", {}).get("result", {})
        if not node:
            continue
        title = str(node.get("title") or "").strip()
        if not title:
            continue
        url = node.get("eventUrl") or ""
        if not url:
            continue

        venue_obj = node.get("venue") or {}
        is_online = node.get("isOnline") or False
        mode = "online" if is_online else ("offline" if venue_obj else None)
        city_name = str(venue_obj.get("city") or "").lower()
        city = None
        if "hyderabad" in city_name:
            city = "hyderabad"
        elif "bangalore" in city_name or "bengaluru" in city_name:
            city = "bangalore"

        group = node.get("group") or {}
        organizer = str(group.get("name") or "").strip() or None

        fee = node.get("feeSettings") or {}
        is_free = (float(fee.get("amount", 0)) == 0.0) if fee else True

        results.append({
            "title": title,
            "description": str(node.get("description") or "")[:300],
            "event_type": "meetup",
            "scope": scope,
            "mode": mode,
            "city": city,
            "venue": str(venue_obj.get("address") or venue_obj.get("name") or "").strip() or None,
            "start_date": node.get("dateTime"),
            "end_date": node.get("endTime"),
            "registration_deadline": None,
            "prize_pool": None,
            "organizer": organizer,
            "registration_url": url,
            "source_name": SOURCE_NAME,
            "source_event_id": str(node.get("id") or url.split("/")[-1]),
            "tags": [],
            "is_student_friendly": False,
            "is_free": is_free,
        })
    return results


def scrape() -> list[dict[str, Any]]:
    if not config.MEETUP_TOKEN:
        logger.info("Meetup: skipped: no key (MEETUP_TOKEN not set)")
        return []

    headers = {
        "Authorization": f"Bearer {config.MEETUP_TOKEN}",
        "Content-Type": "application/json",
    }

    all_results: list[dict] = []
    seen_ids: set[str] = set()

    for loc in _LOCATIONS:
        for keyword in _KEYWORDS:
            cursor = None
            for _ in range(3):  # max 3 pages per keyword+location
                variables: dict[str, Any] = {
                    "lat": loc["lat"],
                    "lon": loc["lon"],
                    "radius": 50.0,
                    "query": keyword,
                    "after": cursor,
                }
                kind, data = fetch(
                    GQL_URL,
                    method="POST",
                    json_body={"query": _GQL_QUERY, "variables": variables},
                    headers=headers,
                    want="json",
                )
                if kind == "error":
                    logger.warning("Meetup GQL error for %s/%s: %s", loc["name"], keyword, data)
                    break

                search = (data or {}).get("data", {}).get("keywordSearch", {})
                edges = search.get("edges", [])
                page_info = search.get("pageInfo", {})

                for ev in _parse_edges(edges, loc["scope"]):
                    eid = ev["source_event_id"]
                    if eid not in seen_ids:
                        seen_ids.add(eid)
                        all_results.append(ev)

                if not page_info.get("hasNextPage"):
                    break
                cursor = page_info.get("endCursor")

    logger.info("Meetup: %d events", len(all_results))
    return all_results
