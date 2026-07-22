"""
config.py — loads .env, exposes typed settings, optional keys, feature flags.
"""
from __future__ import annotations

import os
from pathlib import Path

# ─── locate and load .env (if present) ────────────────────────────────────────
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

def _load_env_file(path: Path) -> None:
    """Minimal .env parser — no external dependency needed."""
    if not path.is_file():
        return
    with path.open(encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)  # don't override existing env vars


_load_env_file(_ENV_FILE)


# ─── helpers ──────────────────────────────────────────────────────────────────
def _get(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


def _require(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            f"Copy .env.example to .env and fill in the value."
        )
    return val


# ─── required ─────────────────────────────────────────────────────────────────
# Default: local MongoDB for zero-config testing; override with Atlas URI in .env
MONGO_URI: str = _get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME: str = _get("MONGO_DB_NAME", "event_radar")

# ─── optional API keys (set to None when absent) ──────────────────────────────
EVENTBRITE_TOKEN: str | None = _get("EVENTBRITE_TOKEN")
MEETUP_TOKEN: str | None = _get("MEETUP_TOKEN")
LUMA_API_KEY: str | None = _get("LUMA_API_KEY")

GEMINI_API_KEY: str | None = _get("GEMINI_API_KEY")
OPENAI_API_KEY: str | None = _get("OPENAI_API_KEY")
ANTHROPIC_API_KEY: str | None = _get("ANTHROPIC_API_KEY")

# ─── feature flags ────────────────────────────────────────────────────────────
# LLM normalization is OFF unless a key is present AND a source is flagged messy
LLM_NORMALIZATION_ENABLED: bool = bool(
    GEMINI_API_KEY or OPENAI_API_KEY or ANTHROPIC_API_KEY
)

# ─── HTTP behaviour ───────────────────────────────────────────────────────────
HTTP_TIMEOUT: int = int(_get("HTTP_TIMEOUT", "15"))       # seconds
HTTP_RETRIES: int = int(_get("HTTP_RETRIES", "3"))
HTTP_BACKOFF_BASE: float = float(_get("HTTP_BACKOFF_BASE", "2.0"))  # seconds
HTTP_PAGE_WAIT: float = float(_get("HTTP_PAGE_WAIT", "2.0"))        # seconds between pages

# ─── runner ───────────────────────────────────────────────────────────────────
RUNNER_MAX_WORKERS: int = int(_get("RUNNER_MAX_WORKERS", "6"))

# ─── dedup ────────────────────────────────────────────────────────────────────
DEDUP_SIMILARITY_THRESHOLD: float = float(_get("DEDUP_SIMILARITY_THRESHOLD", "0.82"))
DEDUP_DATE_WINDOW_DAYS: int = int(_get("DEDUP_DATE_WINDOW_DAYS", "3"))

# ─── corporate seed ───────────────────────────────────────────────────────────
CORPORATE_SEED_WINDOW_DAYS: int = int(_get("CORPORATE_SEED_WINDOW_DAYS", "60"))
