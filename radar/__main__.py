"""CLI entrypoint: `radar` or `python -m radar`."""

from __future__ import annotations

import sys

from radar import __version__
from radar.run import run_pipeline


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    seed = args.seed
    if seed == []:  # --seed with no args -> default calibration set
        from radar.seeds import DEFAULT_NICHES

        seed = DEFAULT_NICHES

    return run_pipeline(keyword=args.keyword, seed=seed, limit_per_niche=args.limit)


if __name__ == "__main__":
    sys.exit(main())
