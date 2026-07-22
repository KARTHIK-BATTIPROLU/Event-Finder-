"""
sources/corporate_seed.py — Static seed of recurring corporate/govt hackathons.

No network calls. Emits entries only when today is within CORPORATE_SEED_WINDOW_DAYS
of the event's window.

Sources confirmed as of 2026 — URLs are official; dates are approximate recurring windows.
event_type = "corporate_challenge" or "program"
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from eventradar import config

logger = logging.getLogger(__name__)

SOURCE_NAME = "corporate_seed"

# Each entry: (title, organizer, event_type, scope, month_start, month_end, url, description, tags)
# month_start / month_end: 1–12 (approximate recurring window months)
_SEED_EVENTS = [
    (
        "Flipkart GRiD",
        "Flipkart",
        "corporate_challenge",
        "india",
        7, 10,
        "https://unstop.com/hackathons/flipkart-grid",
        "Annual engineering hackathon by Flipkart for engineering students.",
        ["ecommerce", "students"],
    ),
    (
        "HackWithInfy",
        "Infosys",
        "corporate_challenge",
        "india",
        2, 7,
        "https://www.infosys.com/careers/hackwithinfy.html",
        "Infosys coding challenge for engineering students.",
        ["students"],
    ),
    (
        "TCS CodeVita",
        "TCS",
        "corporate_challenge",
        "india",
        9, 11,
        "https://www.tcs.com/codevita",
        "World's largest college coding contest by TCS.",
        ["students", "coding"],
    ),
    (
        "Amazon HackOn",
        "Amazon",
        "corporate_challenge",
        "india",
        5, 6,
        "https://hackon.amazon.in/",
        "Annual hackathon by Amazon India for students and professionals.",
        ["cloud", "students"],
    ),
    (
        "Bajaj HackRx",
        "Bajaj Finserv Health",
        "corporate_challenge",
        "india",
        7, 8,
        "https://hackrx.in/",
        "Healthcare technology hackathon by Bajaj Finserv Health.",
        ["healthcare", "data"],
    ),
    (
        "Walmart CodeHers",
        "Walmart",
        "corporate_challenge",
        "india",
        7, 8,
        "https://unstop.com/hackathons/walmart-codehers",
        "Coding competition exclusively for women tech enthusiasts by Walmart.",
        ["women", "coding", "students"],
    ),
    (
        "Adobe Hackathon",
        "Adobe",
        "corporate_challenge",
        "india",
        7, 9,
        "https://www.adobe.com/in/careers/hackathon.html",
        "Annual coding hackathon by Adobe India.",
        ["design", "cloud", "students"],
    ),
    (
        "JPMorgan Code for Good",
        "JPMorgan Chase",
        "corporate_challenge",
        "india",
        3, 3,
        "https://careers.jpmorgan.com/global/en/students/programs/code-for-good",
        "One-day hackathon where students build tech solutions for nonprofits.",
        ["students", "social impact"],
    ),
    (
        "Smart India Hackathon",
        "Ministry of Education, India",
        "corporate_challenge",
        "india",
        8, 12,
        "https://www.sih.gov.in/",
        "India's biggest open innovation model for students.",
        ["government", "students", "social impact"],
    ),
    (
        "Google Solution Challenge",
        "Google Developer Student Clubs",
        "program",
        "global",
        1, 4,
        "https://developers.google.com/community/gdsc-solution-challenge",
        "Annual challenge for GDSC members to solve UN's 17 Sustainable Development Goals.",
        ["google", "students", "social impact"],
    ),
    (
        "Microsoft Imagine Cup",
        "Microsoft",
        "program",
        "global",
        9, 4,
        "https://imaginecup.microsoft.com/",
        "Global technology competition for student developers.",
        ["cloud", "ai", "students"],
    ),
    (
        "NASA Space Apps Challenge",
        "NASA",
        "hackathon",
        "global",
        10, 11,
        "https://www.spaceappschallenge.org/",
        "International hackathon focused on space exploration and Earth challenges.",
        ["space", "data", "students"],
    ),
    (
        "Google Summer of Code",
        "Google",
        "program",
        "global",
        2, 4,
        "https://summerofcode.withgoogle.com/",
        "Global program connecting student developers with open source organizations.",
        ["opensource", "students", "google"],
    ),
    (
        "Hacktoberfest",
        "DigitalOcean",
        "program",
        "global",
        10, 10,
        "https://hacktoberfest.com/",
        "Month-long open source contribution celebration.",
        ["opensource"],
    ),
    (
        "ETHIndia",
        "ETHIndia",
        "hackathon",
        "india",
        11, 12,
        "https://ethindia.co/",
        "India's largest Ethereum hackathon.",
        ["web3", "blockchain", "ethereum"],
    ),
]


def scrape() -> list[dict[str, Any]]:
    today = date.today()
    window = config.CORPORATE_SEED_WINDOW_DAYS
    results: list[dict] = []

    for (
        title, organizer, event_type, scope,
        month_start, month_end, url, description, tags
    ) in _SEED_EVENTS:
        # Build window dates for this calendar year (and next if month wraps)
        year = today.year

        # Handle multi-year windows (e.g., opens Sep, ends Apr next year)
        if month_start <= month_end:
            win_start = date(year, month_start, 1)
            # End = last day of month_end
            if month_end == 12:
                win_end = date(year, 12, 31)
            else:
                win_end = date(year, month_end + 1, 1) - timedelta(days=1)
        else:
            # Spans year boundary
            win_start = date(year, month_start, 1)
            if month_end == 12:
                win_end = date(year + 1, 12, 31)
            else:
                win_end = date(year + 1, month_end + 1, 1) - timedelta(days=1)

        # Emit if today is within WINDOW_DAYS of the window
        in_window = (
            (win_start - timedelta(days=window)) <= today <= (win_end + timedelta(days=window))
        )

        if not in_window:
            # Also check previous year's window
            win_start_prev = date(year - 1, month_start, 1)
            if month_start <= month_end:
                if month_end == 12:
                    win_end_prev = date(year - 1, 12, 31)
                else:
                    win_end_prev = date(year - 1, month_end + 1, 1) - timedelta(days=1)
            else:
                if month_end == 12:
                    win_end_prev = date(year, 12, 31)
                else:
                    win_end_prev = date(year, month_end + 1, 1) - timedelta(days=1)
            in_window = (
                (win_start_prev - timedelta(days=window)) <= today <= (win_end_prev + timedelta(days=window))
            )
            if in_window:
                win_start = win_start_prev
                win_end = win_end_prev

        if not in_window:
            continue

        results.append({
            "title": title,
            "description": description,
            "event_type": event_type,
            "scope": scope,
            "mode": "online",
            "city": None,
            "venue": None,
            "start_date": win_start.isoformat(),
            "end_date": win_end.isoformat(),
            "registration_deadline": None,
            "prize_pool": None,
            "organizer": organizer,
            "registration_url": url,
            "source_name": SOURCE_NAME,
            "source_event_id": title.lower().replace(" ", "_"),
            "tags": tags,
            "is_student_friendly": True,
            "is_free": True,
        })

    logger.info("Corporate seed: %d active events (window=%d days)", len(results), window)
    return results
