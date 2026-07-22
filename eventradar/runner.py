"""
runner.py — Orchestrates the full pipeline:
  1. Resolve which sources to run (apply --only / --skip filters)
  2. Run sources in parallel (ThreadPoolExecutor, max_workers from config)
  3. Normalize each batch through schema.normalize_event
  4. Apply categorize.assign_category and assign_tags
  5. Dedup: within-batch first, then against Mongo
  6. Upsert new events to Mongo
  7. Log each source to scrape_runs
  8. Return a summary table

One broken source NEVER stops other sources — every source is try/except wrapped.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from eventradar import config, db
from eventradar import categorize, dedup as dedup_module, schema
from eventradar.sources import SOURCES, Source

logger = logging.getLogger(__name__)


# ─── result per source ────────────────────────────────────────────────────────

@dataclass
class SourceResult:
    name: str
    items_found: int = 0
    items_stored: int = 0
    status: str = "ok"
    error_message: str | None = None
    duration_s: float = 0.0


# ─── single-source pipeline ───────────────────────────────────────────────────

def _run_source(source: Source, run_at: str) -> SourceResult:
    """
    Run one source end-to-end and return a SourceResult.
    Never raises — all exceptions are caught and recorded.
    """
    result = SourceResult(name=source.name)
    t0 = time.monotonic()

    try:
        # ── 0. key check ──────────────────────────────────────────────
        if source.needs_key:
            import os
            if not os.environ.get(source.needs_key):
                logger.info("Source '%s': skipped: no key (%s)", source.name, source.needs_key)
                result.status = "skipped"
                result.error_message = f"skipped: no key ({source.needs_key} not set)"
                result.duration_s = time.monotonic() - t0
                db.log_run(
                    run_at=run_at,
                    source_name=source.name,
                    items_found=0,
                    items_stored=0,
                    status="skipped",
                    error_message=result.error_message,
                )
                return result

        # ── 1. fetch raw events ───────────────────────────────────────
        raw_events: list[dict[str, Any]] = source.fn()
        result.items_found = len(raw_events)
        logger.info("Source '%s': fetched %d raw events", source.name, result.items_found)

        # ── 2. normalize ──────────────────────────────────────────────
        normalized: list[dict[str, Any]] = []
        for raw in raw_events:
            try:
                raw["source_name"] = source.name  # ensure set
                ev = schema.normalize_event(raw)
                if ev is None:
                    continue
                # ── 3. categorize + tag ───────────────────────────────
                ev["category"] = categorize.assign_category(
                    ev.get("title"), ev.get("description"), ev.get("tags")
                )
                ev["tags"] = categorize.assign_tags(
                    ev.get("title"), ev.get("description"), ev.get("tags")
                )
                ev["is_student_friendly"] = (
                    ev.get("is_student_friendly")
                    or categorize.is_student_friendly(
                        ev.get("title"), ev.get("description"), ev.get("tags")
                    )
                )
                normalized.append(ev)
            except Exception as exc:
                logger.debug("Normalize error for raw event: %s", exc)

        logger.info("Source '%s': %d events after normalization", source.name, len(normalized))

        # ── 4. within-batch dedup ────────────────────────────────────
        deduped_batch = dedup_module.dedup_batch(normalized)

        # ── 5. against-Mongo dedup ───────────────────────────────────
        to_insert = dedup_module.filter_new_events(deduped_batch)

        # ── 6. upsert ────────────────────────────────────────────────
        stored = db.upsert_events(to_insert)
        result.items_stored = stored

        logger.info(
            "Source '%s': %d new events stored (of %d deduplicated)",
            source.name, stored, len(to_insert),
        )

    except Exception as exc:
        result.status = "error"
        result.error_message = str(exc)
        logger.warning("Source '%s' FAILED: %s", source.name, exc, exc_info=True)

    finally:
        result.duration_s = time.monotonic() - t0
        db.log_run(
            run_at=run_at,
            source_name=source.name,
            items_found=result.items_found,
            items_stored=result.items_stored,
            status=result.status,
            error_message=result.error_message,
        )

    return result


# ─── orchestrator ─────────────────────────────────────────────────────────────

def run_pipeline(
    only: list[str] | None = None,
    skip: list[str] | None = None,
    max_workers: int | None = None,
) -> list[SourceResult]:
    """
    Run the full (or filtered) event aggregation pipeline.

    Parameters
    ----------
    only        : if set, run ONLY these source names
    skip        : source names to exclude
    max_workers : thread pool size (default: config.RUNNER_MAX_WORKERS)

    Returns
    -------
    List of SourceResult, one per source that was attempted.
    """
    workers = max_workers if max_workers is not None else config.RUNNER_MAX_WORKERS
    run_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── ensure DB is ready ──────────────────────────────────────────────────
    try:
        db.ensure_indexes()
    except Exception as exc:
        logger.error("Failed to connect to MongoDB or ensure indexes: %s", exc)
        raise

    # ── filter sources ──────────────────────────────────────────────────────
    sources_to_run = list(SOURCES)
    if only:
        only_set = {n.lower() for n in only}
        sources_to_run = [s for s in sources_to_run if s.name.lower() in only_set]
        if not sources_to_run:
            logger.warning("No sources matched --only filter: %s", only)
    if skip:
        skip_set = {n.lower() for n in skip}
        sources_to_run = [s for s in sources_to_run if s.name.lower() not in skip_set]

    if not sources_to_run:
        logger.warning("No sources to run after filtering.")
        return []

    logger.info(
        "Running %d source(s) with %d workers. run_at=%s",
        len(sources_to_run), workers, run_at,
    )

    results: list[SourceResult] = []
    futures_map = {}

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="src") as pool:
        for source in sources_to_run:
            future = pool.submit(_run_source, source, run_at)
            futures_map[future] = source.name

        for future in as_completed(futures_map):
            name = futures_map[future]
            try:
                sr = future.result()
                results.append(sr)
            except Exception as exc:
                logger.error("Unexpected error collecting result for '%s': %s", name, exc)
                results.append(SourceResult(
                    name=name, status="error", error_message=str(exc)
                ))

    # Sort by source order for display
    order = {s.name: i for i, s in enumerate(sources_to_run)}
    results.sort(key=lambda r: order.get(r.name, 9999))

    return results


# ─── summary printer ─────────────────────────────────────────────────────────

def print_summary(results: list[SourceResult]) -> None:
    """Print a formatted results table to stdout."""
    RESET = "\033[0m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"

    header = f"{'Source':<20} {'Found':>7} {'Stored':>7} {'Status':<12} {'Time':>6}"
    divider = "-" * len(header)

    print()
    print(f"{BOLD}{CYAN}{header}{RESET}")
    print(CYAN + divider + RESET)

    total_found = 0
    total_stored = 0

    for r in results:
        if r.status == "ok":
            color = GREEN
        elif r.status == "skipped":
            color = YELLOW
        else:
            color = RED

        status_display = r.status
        if r.status == "error" and r.error_message:
            status_display = f"error: {r.error_message[:30]}"

        print(
            f"{r.name:<20} {r.items_found:>7} {r.items_stored:>7} "
            f"{color}{status_display:<12}{RESET} {r.duration_s:>5.1f}s"
        )
        total_found += r.items_found
        total_stored += r.items_stored

    print(CYAN + divider + RESET)
    print(
        f"{'TOTAL':<20} {total_found:>7} {total_stored:>7}"
    )
    print()
