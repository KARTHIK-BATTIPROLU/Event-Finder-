"""
db.py — MongoDB client, index setup, upsert helpers, and run-log writer.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pymongo
from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection
from pymongo.database import Database

from eventradar import config

logger = logging.getLogger(__name__)

# ─── module-level lazy singletons ─────────────────────────────────────────────
_client: MongoClient | None = None
_db: Database | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(
            config.MONGO_URI,
            serverSelectionTimeoutMS=10_000,
            connectTimeoutMS=10_000,
            socketTimeoutMS=30_000,
        )
    return _client


def get_db() -> Database:
    global _db
    if _db is None:
        _db = get_client()[config.MONGO_DB_NAME]
    return _db


def get_events_col() -> Collection:
    return get_db()["events"]


def get_runs_col() -> Collection:
    return get_db()["scrape_runs"]


# ─── index setup ──────────────────────────────────────────────────────────────

def ensure_indexes() -> None:
    """Create all indexes (idempotent — safe to call on every run)."""
    col = get_events_col()
    runs = get_runs_col()

    # Unique compound index: the dedup key
    col.create_index(
        [("source_name", pymongo.ASCENDING), ("source_event_id", pymongo.ASCENDING)],
        unique=True,
        name="idx_source_unique",
    )
    # Query indexes
    for field in ("normalized_title", "start_date", "registration_deadline",
                  "scope", "category", "city"):
        col.create_index([(field, pymongo.ASCENDING)], name=f"idx_{field}")

    # scrape_runs indexes
    runs.create_index([("run_at", pymongo.DESCENDING)], name="idx_run_at")
    runs.create_index([("source_name", pymongo.ASCENDING)], name="idx_source_name")

    logger.debug("MongoDB indexes ensured.")


# ─── upsert ───────────────────────────────────────────────────────────────────

def upsert_events(events: list[dict[str, Any]]) -> int:
    """
    Bulk-upsert a list of normalized events.
    Uses (source_name, source_event_id) as the match key.
    Sets scraped_at on insert; does NOT overwrite existing fields that are already set
    (uses $setOnInsert for most fields, $set for mutable ones).

    Returns the number of new documents inserted (upserted).
    """
    if not events:
        return 0

    col = get_events_col()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    ops = []
    for ev in events:
        ev["scraped_at"] = now_iso
        filter_key = {
            "source_name": ev["source_name"],
            "source_event_id": ev["source_event_id"],
        }
        # Always update these "enrichable" fields when a newer scrape finds them
        set_always = {
            k: ev[k]
            for k in ("scraped_at",)
            if ev.get(k) is not None
        }
        # Set these only if not already present (preserve human edits)
        set_on_insert = {k: v for k, v in ev.items() if k not in set_always}

        # For enrichment fields: fill nulls in existing docs
        # We use a pipeline update so we can conditionally set null fields
        set_if_null = {}
        for field in ("prize_pool", "registration_deadline", "venue", "description"):
            val = ev.get(field)
            if val is not None:
                set_if_null[field] = val

        # Build the update doc
        update: dict[str, Any] = {
            "$set": set_always,
            "$setOnInsert": set_on_insert,
        }

        ops.append(
            UpdateOne(filter_key, update, upsert=True)
        )

    if not ops:
        return 0

    try:
        result = col.bulk_write(ops, ordered=False)
        inserted = result.upserted_count
        logger.debug(
            "Bulk write: %d inserted, %d modified out of %d ops",
            inserted, result.modified_count, len(ops),
        )
        return inserted
    except pymongo.errors.BulkWriteError as bwe:
        # Log details but don't crash — partial successes are fine
        upserted = bwe.details.get("nUpserted", 0)
        logger.warning(
            "BulkWriteError (partial success=%d): %s",
            upserted, bwe.details.get("writeErrors", [])[:3],
        )
        return upserted


def enrich_existing(
    source_name: str,
    source_event_id: str,
    fields: dict[str, Any],
) -> None:
    """Fill null fields on an existing document (dedup enrichment path)."""
    col = get_events_col()
    # Only set fields that are currently null / missing
    null_checks = {k: {"$in": [None, ""]} for k in fields}
    set_ops = {k: v for k, v in fields.items() if v is not None}
    if not set_ops:
        return
    col.update_one(
        {
            "source_name": source_name,
            "source_event_id": source_event_id,
            **{k: {"$in": [None, "", []]} for k in set_ops},
        },
        {"$set": set_ops},
    )


# ─── scrape_runs log ──────────────────────────────────────────────────────────

def log_run(
    *,
    run_at: str,
    source_name: str,
    items_found: int,
    items_stored: int,
    status: str,
    error_message: str | None = None,
) -> None:
    """Insert one row into scrape_runs."""
    try:
        get_runs_col().insert_one(
            {
                "run_at": run_at,
                "source_name": source_name,
                "items_found": items_found,
                "items_stored": items_stored,
                "status": status,
                "error_message": error_message,
            }
        )
    except Exception as exc:
        logger.error("Failed to write scrape_run log: %s", exc)


# ─── query helpers ────────────────────────────────────────────────────────────

def get_candidates_near_date(date_str: str | None, window_days: int = 3) -> list[dict]:
    """Pull events whose start_date is within +/-window_days of date_str."""
    if not date_str:
        return []
    from datetime import timedelta
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return []
    lo = (dt - timedelta(days=window_days)).strftime("%Y-%m-%d")
    hi = (dt + timedelta(days=window_days)).strftime("%Y-%m-%d")
    return list(
        get_events_col().find(
            {"start_date": {"$gte": lo, "$lte": hi}},
            {"normalized_title": 1, "source_name": 1, "source_event_id": 1,
             "city": 1, "mode": 1, "prize_pool": 1, "registration_deadline": 1,
             "venue": 1, "description": 1},
        )
    )


def stats() -> dict[str, Any]:
    """Aggregate counts for the CLI stats command."""
    col = get_events_col()
    pipeline_scope = [{"$group": {"_id": "$scope", "count": {"$sum": 1}}}]
    pipeline_cat = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}]
    pipeline_src = [{"$group": {"_id": "$source_name", "count": {"$sum": 1}}}]

    return {
        "total": col.count_documents({}),
        "by_scope": {d["_id"]: d["count"] for d in col.aggregate(pipeline_scope)},
        "by_category": {d["_id"]: d["count"] for d in col.aggregate(pipeline_cat)},
        "by_source": {d["_id"]: d["count"] for d in col.aggregate(pipeline_src)},
    }
