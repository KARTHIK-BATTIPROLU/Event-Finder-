#!/usr/bin/env python3
"""
main.py — EventRadar CLI entrypoint.

Commands:
  python main.py run                  # full pipeline
  python main.py run --only luma      # single source (repeatable)
  python main.py run --skip meetup    # exclude a source
  python main.py sources              # list registered sources
  python main.py stats                # MongoDB aggregate stats
"""
from __future__ import annotations

import argparse
import logging
import sys


def _setup_logging(verbose: bool = False) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    # Quiet down noisy libraries
    for noisy in ("urllib3", "pymongo", "requests"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ─── sub-commands ─────────────────────────────────────────────────────────────

def cmd_run(args: argparse.Namespace) -> int:
    from eventradar.runner import run_pipeline, print_summary

    only = args.only or []
    skip = args.skip or []

    try:
        results = run_pipeline(only=only or None, skip=skip or None)
    except Exception as exc:
        print(f"\n[!] Fatal error: {exc}", file=sys.stderr)
        return 1

    print_summary(results)

    errors = [r for r in results if r.status == "error"]
    if errors:
        print(f"[!] {len(errors)} source(s) failed — see log above for details.")
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    from eventradar.sources import SOURCES

    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[96m"
    YELLOW = "\033[93m"

    header = f"{'Name':<22} {'Needs Key':<20} {'Key-gated?'}"
    divider = "-" * 55
    print(f"\n{BOLD}{CYAN}{header}{RESET}")
    print(CYAN + divider + RESET)
    for s in SOURCES:
        key_flag = f"{YELLOW}yes ({s.needs_key}){RESET}" if s.needs_key else "no"
        print(f"{s.name:<22} {s.needs_key or 'none':<20} {key_flag}")
    print()
    print(f"Total: {len(SOURCES)} source(s)")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    from eventradar import db

    try:
        db.ensure_indexes()
        data = db.stats()
    except Exception as exc:
        print(f"❌ MongoDB error: {exc}", file=sys.stderr)
        return 1

    BOLD = "\033[1m"
    CYAN = "\033[96m"
    RESET = "\033[0m"

    print(f"\n{BOLD}EventRadar — MongoDB Stats{RESET}")
    print(f"  Total events: {BOLD}{data['total']}{RESET}\n")

    print(f"  {CYAN}By Scope:{RESET}")
    for scope, count in sorted(data["by_scope"].items()):
        print(f"    {scope:<15} {count:>6}")

    print(f"\n  {CYAN}By Category:{RESET}")
    for cat, count in sorted(data["by_category"].items()):
        print(f"    {cat:<15} {count:>6}")

    print(f"\n  {CYAN}By Source:{RESET}")
    for src, count in sorted(data["by_source"].items(), key=lambda x: -x[1]):
        print(f"    {src:<22} {count:>6}")

    print()
    return 0


# ─── parser setup ─────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eventradar",
        description="EventRadar — tech/founder/networking event aggregator",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    # run
    run_p = sub.add_parser("run", help="Run the event scraping pipeline")
    run_p.add_argument(
        "--only", metavar="SOURCE", action="append", default=[],
        help="Run only this source (repeatable, e.g. --only luma --only devpost)",
    )
    run_p.add_argument(
        "--skip", metavar="SOURCE", action="append", default=[],
        help="Skip this source (repeatable)",
    )

    # sources
    sub.add_parser("sources", help="List all registered sources")

    # stats
    sub.add_parser("stats", help="Show MongoDB aggregate statistics")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _setup_logging(args.verbose)

    dispatch = {
        "run": cmd_run,
        "sources": cmd_sources,
        "stats": cmd_stats,
    }
    fn = dispatch.get(args.command)
    if fn is None:
        parser.print_help()
        sys.exit(1)

    sys.exit(fn(args))


if __name__ == "__main__":
    main()
