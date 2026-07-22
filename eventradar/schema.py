"""
schema.py — Event dataclass + normalization helpers.

Every scraper returns a list of plain dicts that conform to the SCHEMA_KEYS shape.
normalize_event() fills defaults and coerces types.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, date
from typing import Any

# ─── canonical key set ────────────────────────────────────────────────────────
SCHEMA_KEYS = [
    "title",
    "normalized_title",
    "description",
    "event_type",
    "category",
    "scope",
    "mode",
    "city",
    "venue",
    "start_date",
    "end_date",
    "registration_deadline",
    "prize_pool",
    "organizer",
    "registration_url",
    "source_name",
    "source_event_id",
    "tags",
    "is_student_friendly",
    "is_free",
    "scraped_at",
]

VALID_EVENT_TYPES = {
    "hackathon", "meetup", "conference",
    "corporate_challenge", "program", "workshop",
}

VALID_CATEGORIES = {"tech", "founder", "networking"}
VALID_SCOPES = {"hyderabad", "india", "global"}
VALID_MODES = {"online", "offline", "hybrid"}


# ─── helpers ──────────────────────────────────────────────────────────────────

def slugify_title(text: str) -> str:
    """
    Lower-case, strip accents, remove non-alphanumeric except spaces,
    collapse multiple spaces — used as normalized_title.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_date(raw: Any) -> str | None:
    """
    Best-effort ISO date (YYYY-MM-DD) from a variety of input formats.
    Returns the raw string if parsing fails, or None if empty.
    """
    if raw is None:
        return None
    if isinstance(raw, (datetime,)):
        return raw.strftime("%Y-%m-%d")
    if isinstance(raw, date):
        return raw.isoformat()
    if isinstance(raw, (int, float)):
        # Unix timestamp
        try:
            return datetime.utcfromtimestamp(raw).strftime("%Y-%m-%d")
        except (OSError, OverflowError, ValueError):
            return None
    raw = str(raw).strip()
    if not raw:
        return None
    # Try common patterns
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%Y/%m/%d",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Return the raw string as-is if we can't parse it
    return raw


def truncate_description(text: str | None, max_len: int = 300) -> str | None:
    """Trim description to max_len characters."""
    if not text:
        return None
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len - 1].rstrip() + "…"


def make_source_event_id(title: str, start_date: str | None) -> str:
    """Fallback source_event_id: slug of title + start_date."""
    parts = [slugify_title(title)]
    if start_date:
        parts.append(re.sub(r"[^0-9]", "", start_date[:10]))
    return "_".join(p for p in parts if p)[:200]


def normalize_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    """
    Coerce a raw scraper dict into the canonical schema.
    Returns None if the event is missing required fields (registration_url or source_event_id).
    """
    ev: dict[str, Any] = {}

    # ── required: registration_url ──
    url = raw.get("registration_url") or ""
    if not url or not url.startswith("http"):
        return None  # drop silently — no URL, no point storing

    ev["registration_url"] = url.strip()

    # ── title ──
    title = str(raw.get("title") or "").strip()
    if not title:
        return None
    ev["title"] = title
    ev["normalized_title"] = slugify_title(title)

    # ── source_event_id ──
    raw_id = raw.get("source_event_id") or ""
    ev["source_event_id"] = (
        str(raw_id).strip() if raw_id else make_source_event_id(title, raw.get("start_date"))
    )
    if not ev["source_event_id"]:
        return None

    # ── source_name ──
    ev["source_name"] = str(raw.get("source_name") or "unknown").strip()

    # ── description ──
    ev["description"] = truncate_description(raw.get("description"))

    # ── event_type ──
    raw_type = str(raw.get("event_type") or "").lower().strip()
    ev["event_type"] = raw_type if raw_type in VALID_EVENT_TYPES else "hackathon"

    # ── category ──
    raw_cat = str(raw.get("category") or "").lower().strip()
    ev["category"] = raw_cat if raw_cat in VALID_CATEGORIES else "tech"

    # ── scope ──
    raw_scope = str(raw.get("scope") or "").lower().strip()
    ev["scope"] = raw_scope if raw_scope in VALID_SCOPES else "global"

    # ── mode ──
    raw_mode = str(raw.get("mode") or "").lower().strip()
    ev["mode"] = raw_mode if raw_mode in VALID_MODES else None

    # ── city ──
    raw_city = str(raw.get("city") or "").lower().strip()
    ev["city"] = raw_city if raw_city in {"hyderabad", "bangalore", "other"} else None

    # ── venue ──
    ev["venue"] = str(raw.get("venue") or "").strip() or None

    # ── dates ──
    ev["start_date"] = parse_date(raw.get("start_date"))
    ev["end_date"] = parse_date(raw.get("end_date"))
    ev["registration_deadline"] = parse_date(raw.get("registration_deadline"))

    # ── prize_pool ──
    ev["prize_pool"] = str(raw.get("prize_pool") or "").strip() or None

    # ── organizer ──
    ev["organizer"] = str(raw.get("organizer") or "").strip() or None

    # ── tags ──
    raw_tags = raw.get("tags") or []
    ev["tags"] = [str(t).lower().strip() for t in raw_tags if t]

    # ── flags ──
    sf = raw.get("is_student_friendly")
    ev["is_student_friendly"] = bool(sf) if sf is not None else False

    is_free = raw.get("is_free")
    ev["is_free"] = bool(is_free) if is_free is not None else None

    # ── scraped_at — will be set by db.py at upsert time ──
    ev["scraped_at"] = raw.get("scraped_at") or datetime.utcnow().strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    return ev
