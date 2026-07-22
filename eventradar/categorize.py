"""
categorize.py — Deterministic keyword-based category + tag assignment.

No LLM involved.  Runs on title + description + existing tags combined.
"""
from __future__ import annotations

import re

# ─── category keyword sets ────────────────────────────────────────────────────
_FOUNDER_KEYWORDS = frozenset({
    "founder", "startup", "pitch", "demo day", "vc", "fundraising",
    "incubator", "accelerator", "entrepreneur", "entrepreneurship",
    "seed funding", "series a", "angel", "venture", "investor",
    "product launch", "go-to-market",
})

_NETWORKING_KEYWORDS = frozenset({
    "meetup", "mixer", "networking", "community", "social", "connect",
    "happy hour", "drinks", "after party", "roundtable", "fireside",
})

# tech is the default — anything that isn't clearly founder or networking

# ─── tag keyword sets ─────────────────────────────────────────────────────────
_TAG_KEYWORDS: dict[str, set[str]] = {
    "ai":          {"ai", "artificial intelligence", "llm", "genai", "gen ai",
                    "machine learning", "deep learning"},
    "ml":          {"machine learning", "ml", "neural network", "nlp",
                    "natural language processing", "computer vision"},
    "web3":        {"web3", "web 3", "defi", "nft", "dao", "dapp"},
    "blockchain":  {"blockchain", "crypto", "cryptocurrency", "solidity",
                    "ethereum", "bitcoin", "polygon"},
    "cloud":       {"cloud", "aws", "azure", "gcp", "kubernetes", "docker",
                    "devops", "serverless", "microservices"},
    "security":    {"security", "cybersecurity", "ctf", "hacking", "pentest",
                    "infosec", "vulnerability", "firewall"},
    "data":        {"data", "analytics", "data science", "big data",
                    "data engineering", "sql", "database"},
    "mobile":      {"mobile", "android", "ios", "flutter", "react native",
                    "swift", "kotlin"},
    "web":         {"web", "frontend", "backend", "fullstack", "javascript",
                    "react", "nextjs", "typescript"},
    "opensource":  {"open source", "opensource", "github", "git", "foss"},
    "women":       {"women", "girls", "female", "diversity", "inclusion",
                    "she codes", "women who code", "techher"},
    "students":    {"student", "college", "university", "campus", "undergrad",
                    "graduate", "intern", "fresher"},
    "startup":     {"startup", "founder", "entrepreneur", "incubator",
                    "accelerator"},
    "gamedev":     {"game", "gaming", "unity", "unreal", "gamejam", "game jam",
                    "game development"},
    "iot":         {"iot", "internet of things", "embedded", "arduino",
                    "raspberry pi", "sensors"},
    "hardware":    {"hardware", "robotics", "robot", "drone", "3d print",
                    "circuit", "embedded systems"},
}


def _tokenize(text: str) -> str:
    """Lower-case and collapse whitespace for keyword matching."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def _text_corpus(*fields: str | None) -> str:
    """Combine multiple optional text fields into one string for matching."""
    return " ".join(f for f in fields if f)


def assign_category(
    title: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """
    Returns "founder" | "networking" | "tech".
    Founder takes priority over networking.
    """
    corpus = _tokenize(_text_corpus(title, description, *(tags or [])))

    for kw in _FOUNDER_KEYWORDS:
        # Use word-boundary-ish check: keyword surrounded by non-word chars or string ends
        pattern = r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])"
        if re.search(pattern, corpus):
            return "founder"

    for kw in _NETWORKING_KEYWORDS:
        pattern = r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])"
        if re.search(pattern, corpus):
            return "networking"

    return "tech"


def assign_tags(
    title: str | None = None,
    description: str | None = None,
    existing_tags: list[str] | None = None,
) -> list[str]:
    """
    Returns a de-duped, sorted list of lowercase technology/topic tags.
    """
    corpus = _tokenize(_text_corpus(title, description, *(existing_tags or [])))
    found: set[str] = set(existing_tags or [])

    for tag, keywords in _TAG_KEYWORDS.items():
        for kw in keywords:
            pattern = r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])"
            if re.search(pattern, corpus):
                found.add(tag)
                break  # one match per tag is enough

    return sorted(found)


def is_student_friendly(
    title: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> bool:
    """Heuristic: true if any student-oriented keyword is present."""
    corpus = _tokenize(_text_corpus(title, description, *(tags or [])))
    student_kws = _TAG_KEYWORDS["students"] | {"student friendly", "open to all",
                                                "for students", "hackathon"}
    for kw in student_kws:
        pattern = r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])"
        if re.search(pattern, corpus):
            return True
    return False
