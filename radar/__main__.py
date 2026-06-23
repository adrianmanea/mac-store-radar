"""CLI entrypoint: `radar` or `python -m radar`."""

from __future__ import annotations

import sys

from radar import __version__
from radar.run import (
    run_charts_job,
    run_dedup_job,
    run_discovery_job,
    run_export,
    run_pipeline,
    run_tagging,
    run_trends_job,
    run_watch,
)


def build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        prog="radar",
        description="Mac App Opportunity Radar — scrape + score the Mac App Store.",
    )
    parser.add_argument("--version", action="version", version=f"radar {__version__}")
    parser.add_argument("--keyword", "-k", help="Score a single keyword (live probe; later).")
    parser.add_argument(
        "--seed",
        nargs="*",
        help="Seed these niche keywords before scraping (idempotent). "
        "Pass with no values to seed the default calibration set.",
    )
    parser.add_argument(
        "--limit", type=int, default=50, help="Max apps per niche search (default 50)."
    )
    parser.add_argument(
        "--tag",
        nargs="?",
        type=int,
        const=50,
        help="Run the decoupled buildability tagging job on up to N untagged apps "
        "(default 50) instead of scraping. Requires ANTHROPIC_API_KEY.",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Run the discovery job: Google Suggest (+ Claude if key set) generates "
        "candidate niches, each validated + scored, winners auto-promote into the "
        "watch list.",
    )
    parser.add_argument(
        "--export",
        metavar="DIR",
        help="Export all tables to JSONL in DIR (backup), then exit.",
    )
    parser.add_argument(
        "--watch",
        nargs="+",
        metavar="KEYWORD",
        help="Add discovered candidate keyword(s) to the watch list (daily-tracked).",
    )
    parser.add_argument(
        "--dedup",
        action="store_true",
        help="Collapse candidate niches that resolve to the same competitive set.",
    )
    parser.add_argument(
        "--charts",
        action="store_true",
        help="Ingest the top-free Mac chart (new/young entrants) into the catalog.",
    )
    parser.add_argument(
        "--trends",
        action="store_true",
        help="Recompute per-app rating velocity from snapshots.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.charts:
        return run_charts_job()
    if args.trends:
        return run_trends_job()
    if args.dedup:
        return run_dedup_job()
    if args.watch:
        return run_watch(args.watch)
    if args.export:
        return run_export(args.export)
    if args.discover:
        return run_discovery_job()
    if args.tag is not None:
        return run_tagging(cap=args.tag)

    seed = args.seed
    if seed == []:  # --seed with no args -> default calibration set
        from radar.seeds import DEFAULT_NICHES

        seed = DEFAULT_NICHES

    return run_pipeline(keyword=args.keyword, seed=seed, limit_per_niche=args.limit)


if __name__ == "__main__":
    sys.exit(main())
