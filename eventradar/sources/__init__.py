"""
sources/__init__.py — Registry of all event sources.

Each entry is a namedtuple:
  Source(name, fn, needs_key)
    name       str   — identifier used in CLI and DB
    fn         callable[[], list[dict]]  — returns raw event dicts
    needs_key  str | None  — env-var name required, or None if key-free
"""
from __future__ import annotations

from typing import Callable, NamedTuple


class Source(NamedTuple):
    name: str
    fn: Callable[[], list[dict]]
    needs_key: str | None = None


def _build_registry() -> list[Source]:
    # Import lazily inside the function so that import errors in one source
    # don't break the whole registry.
    from eventradar.sources import (
        luma,
        devfolio,
        devpost,
        unstop,
        hackerearth,
        mlh,
        devevents,
        knowafest,
        reskilll,
        hack2skill,
        lablab,
        commudle,
        allevents,
        townscript,
        konfhub,
        gdg_hyderabad,
        eventbrite,
        meetup,
        luma_api,
        corporate_seed,
    )

    return [
        # ── no-key sources ──────────────────────────────────────────────────
        Source("luma",           luma.scrape,           None),
        Source("devfolio",       devfolio.scrape,       None),
        Source("devpost",        devpost.scrape,        None),
        Source("unstop",         unstop.scrape,         None),
        Source("hackerearth",    hackerearth.scrape,    None),
        Source("mlh",            mlh.scrape,            None),
        Source("devevents",      devevents.scrape,      None),
        Source("knowafest",      knowafest.scrape,      None),
        Source("reskilll",       reskilll.scrape,       None),
        Source("hack2skill",     hack2skill.scrape,     None),
        Source("lablab",         lablab.scrape,         None),
        Source("commudle",       commudle.scrape,       None),
        Source("allevents",      allevents.scrape,      None),
        Source("townscript",     townscript.scrape,     None),
        Source("konfhub",        konfhub.scrape,        None),
        Source("gdg_hyderabad",  gdg_hyderabad.scrape,  None),
        Source("corporate_seed", corporate_seed.scrape, None),
        # ── key-gated sources ───────────────────────────────────────────────
        Source("eventbrite",     eventbrite.scrape,     "EVENTBRITE_TOKEN"),
        Source("meetup",         meetup.scrape,         "MEETUP_TOKEN"),
        Source("luma_api",       luma_api.scrape,       "LUMA_API_KEY"),
    ]


# Build once at import time — any broken import is caught per-source in runner.py
try:
    SOURCES: list[Source] = _build_registry()
except Exception as _e:
    import logging
    logging.getLogger(__name__).error("Failed to build source registry: %s", _e)
    SOURCES = []
