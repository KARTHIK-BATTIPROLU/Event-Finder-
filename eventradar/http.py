"""
http.py — Resilient HTTP fetch with retries, timeout, User-Agent rotation,
and per-page wait.  Returns a (kind, data) tuple where:
  kind = "json"  -> data is a parsed dict/list
  kind = "html"  -> data is a BeautifulSoup object
  kind = "text"  -> data is raw text
  kind = "error" -> data is an error string (caller should log and continue)
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

from eventradar import config

logger = logging.getLogger(__name__)

# Rotate through a few real UA strings so individual requests look organic
_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
]

_ua_index = 0


def _next_ua() -> str:
    global _ua_index
    ua = _USER_AGENTS[_ua_index % len(_USER_AGENTS)]
    _ua_index += 1
    return ua


def _build_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": _next_ua(),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }
    if extra:
        headers.update(extra)
    return headers


def fetch(
    url: str,
    *,
    method: str = "GET",
    params: dict | None = None,
    json_body: dict | None = None,
    headers: dict[str, str] | None = None,
    want: str = "auto",          # "json" | "html" | "text" | "auto"
    timeout: int | None = None,
    retries: int | None = None,
    backoff_base: float | None = None,
    page_wait: float | None = None,
    session: requests.Session | None = None,
) -> tuple[str, Any]:
    """
    Fetch a URL with retry logic.

    Parameters
    ----------
    url         : full URL to fetch
    method      : HTTP verb ("GET" or "POST")
    params      : query-string parameters
    json_body   : JSON body for POST
    headers     : additional request headers (merged with defaults)
    want        : "json", "html", "text", or "auto" (sniff Content-Type)
    timeout     : seconds; falls back to config.HTTP_TIMEOUT
    retries     : number of attempts; falls back to config.HTTP_RETRIES
    backoff_base: seconds base for exponential backoff
    page_wait   : seconds to sleep BEFORE the first request (useful for pagination loops)
    session     : reuse a requests.Session if provided

    Returns
    -------
    ("json"  , dict | list)       on JSON success
    ("html"  , BeautifulSoup)     on HTML success
    ("text"  , str)               on text success
    ("error" , str)               on final failure — caller must handle
    """
    _timeout = timeout if timeout is not None else config.HTTP_TIMEOUT
    _retries = retries if retries is not None else config.HTTP_RETRIES
    _backoff = backoff_base if backoff_base is not None else config.HTTP_BACKOFF_BASE
    _wait = page_wait if page_wait is not None else 0.0

    if _wait > 0:
        time.sleep(_wait)

    merged_headers = _build_headers(headers)
    if want == "json" or (want == "auto"):
        merged_headers.setdefault("Accept", "application/json, text/html, */*")

    caller = session or requests

    last_error: str = "unknown error"
    for attempt in range(1, _retries + 1):
        try:
            resp = caller.request(  # type: ignore[attr-defined]
                method.upper(),
                url,
                params=params,
                json=json_body,
                headers=merged_headers,
                timeout=_timeout,
            )
            resp.raise_for_status()

            # ── detect format ──────────────────────────────────────────
            ct = resp.headers.get("Content-Type", "")
            resolved_want = want

            if resolved_want == "auto":
                if "json" in ct:
                    resolved_want = "json"
                elif "html" in ct or "xml" in ct:
                    resolved_want = "html"
                else:
                    # Try JSON first, fall back to HTML
                    try:
                        return ("json", resp.json())
                    except Exception:
                        resolved_want = "html"

            if resolved_want == "json":
                try:
                    return ("json", resp.json())
                except Exception as exc:
                    return ("error", f"JSON decode error from {url}: {exc}")

            if resolved_want == "html":
                soup = BeautifulSoup(resp.text, "html.parser")
                return ("html", soup)

            return ("text", resp.text)

        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            last_error = f"HTTP {status} for {url}"
            if exc.response is not None and exc.response.status_code in (403, 404, 410):
                # Non-retryable client errors
                logger.debug("Non-retryable %s", last_error)
                return ("error", last_error)
            logger.warning("Attempt %d/%d failed: %s", attempt, _retries, last_error)

        except requests.exceptions.Timeout:
            last_error = f"Timeout ({_timeout}s) for {url}"
            logger.warning("Attempt %d/%d — %s", attempt, _retries, last_error)

        except requests.exceptions.ConnectionError as exc:
            last_error = f"Connection error for {url}: {exc}"
            logger.warning("Attempt %d/%d — %s", attempt, _retries, last_error)

        except Exception as exc:
            last_error = f"Unexpected error for {url}: {exc}"
            logger.warning("Attempt %d/%d — %s", attempt, _retries, last_error)

        if attempt < _retries:
            sleep_time = _backoff * (2 ** (attempt - 1))
            logger.debug("Sleeping %.1fs before retry…", sleep_time)
            time.sleep(sleep_time)

    return ("error", last_error)


def make_session() -> requests.Session:
    """Return a persistent session (useful when a source needs cookies)."""
    s = requests.Session()
    s.headers.update(_build_headers())
    return s
