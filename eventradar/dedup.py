"""
dedup.py — Bigram Dice-coefficient similarity + duplicate detection.

Dedup pipeline:
  1. Within the batch: drop items that share normalized_title + start_date.
  2. Against Mongo: fetch candidates within +/-3 days of start_date.
  3. Dice coefficient on normalized_title >= threshold AND city/mode match
     -> considered duplicate.
  4. On duplicate: enrich existing document's null fields instead of inserting.
"""
from __future__ import annotations

import logging
from typing import Any

from eventradar import config, db

logger = logging.getLogger(__name__)


# ─── bigram helpers ───────────────────────────────────────────────────────────

def _bigrams(text: str) -> set[str]:
    """Return the set of character bigrams of a string."""
    if len(text) < 2:
        return {text} if text else set()
    return {text[i:i+2] for i in range(len(text) - 1)}


def dice_similarity(a: str, b: str) -> float:
    """
    Sørensen–Dice coefficient on character bigrams.
    Returns a float in [0.0, 1.0].
    """
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    bg_a = _bigrams(a)
    bg_b = _bigrams(b)
    intersection = len(bg_a & bg_b)
    return (2 * intersection) / (len(bg_a) + len(bg_b))


# ─── within-batch dedup ───────────────────────────────────────────────────────

def dedup_batch(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Drop within-batch duplicates: keep the first occurrence when
    normalized_title + start_date are identical.
    Returns the deduplicated list (order preserved).
    """
    seen: set[tuple[str, str | None]] = set()
    out: list[dict[str, Any]] = []
    for ev in events:
        key = (ev.get("normalized_title", ""), ev.get("start_date"))
        if key in seen:
            logger.debug(
                "In-batch duplicate dropped: '%s' (%s)",
                ev.get("title"), ev.get("start_date"),
            )
            continue
        seen.add(key)
        out.append(ev)
    return out


# ─── against-Mongo dedup ──────────────────────────────────────────────────────

def _location_matches(ev: dict[str, Any], candidate: dict[str, Any]) -> bool:
    """
    Returns True if the two events could be the same event geographically:
      - either event is online, OR
      - both events have the same city (or at least one has None).
    """
    if ev.get("mode") == "online" or candidate.get("mode") == "online":
        return True
    c1 = ev.get("city")
    c2 = candidate.get("city")
    if c1 is None or c2 is None:
        return True  # insufficient info — don't suppress
    return c1 == c2


def is_duplicate(
    ev: dict[str, Any],
    candidates: list[dict[str, Any]],
    threshold: float | None = None,
) -> tuple[bool, dict[str, Any] | None]:
    """
    Check whether *ev* is a duplicate of any candidate.

    Returns (True, matching_candidate) or (False, None).
    """
    th = threshold if threshold is not None else config.DEDUP_SIMILARITY_THRESHOLD
    norm_title = ev.get("normalized_title", "")
    if not norm_title:
        return False, None

    for cand in candidates:
        cand_title = cand.get("normalized_title", "")
        sim = dice_similarity(norm_title, cand_title)
        if sim >= th and _location_matches(ev, cand):
            logger.debug(
                "Duplicate detected: '%.60s' ~ '%.60s' (sim=%.3f)",
                ev.get("title"), cand.get("normalized_title"), sim,
            )
            return True, cand

    return False, None


# ─── enrichment after dedup ───────────────────────────────────────────────────

_ENRICHABLE_FIELDS = ("prize_pool", "registration_deadline", "venue", "description")


def enrich_if_duplicate(
    ev: dict[str, Any],
    existing: dict[str, Any],
) -> None:
    """Fill null fields on the existing MongoDB document from the new event."""
    fields: dict[str, Any] = {}
    for field in _ENRICHABLE_FIELDS:
        new_val = ev.get(field)
        old_val = existing.get(field)
        if new_val and not old_val:
            fields[field] = new_val
    if fields:
        db.enrich_existing(
            source_name=existing["source_name"],
            source_event_id=existing["source_event_id"],
            fields=fields,
        )
        logger.debug(
            "Enriched existing event '%s' with %s",
            existing.get("normalized_title"), list(fields.keys()),
        )


# ─── main dedup filter for a run ─────────────────────────────────────────────

def filter_new_events(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Given a normalized, within-batch-deduped list, remove any event that
    already exists in Mongo (by title similarity + date proximity).
    Enriches duplicates in-place.

    Returns the subset that should be inserted.
    """
    to_insert: list[dict[str, Any]] = []
    window = config.DEDUP_DATE_WINDOW_DAYS

    for ev in events:
        candidates = db.get_candidates_near_date(ev.get("start_date"), window)
        dup, existing = is_duplicate(ev, candidates)
        if dup and existing:
            enrich_if_duplicate(ev, existing)
        else:
            to_insert.append(ev)
    return to_insert
