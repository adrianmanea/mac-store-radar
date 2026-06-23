"""Pipeline run entrypoint (M5).

Builds the real clients (Supabase service client + throttled iTunes client) and runs a
scrape pass. The scrape orchestration itself lives in radar.pipeline.scrape.
"""

from __future__ import annotations

import logging

from radar import __version__
from radar.adapters.client import ITunesClient
from radar.adapters.limiter import TokenBucket
from radar.adapters.rawstore import FileRawStore
from radar.config import Config
from radar.db import writers
from radar.db.client import service_client
from radar.pipeline.score import score_all_niches
from radar.pipeline.scrape import run_scrape
from radar.scoring.weights import load_weights


def _itunes_client(cfg: Config) -> ITunesClient:
    return ITunesClient(
        limiter=TokenBucket(per_minute=cfg.rate_limit_per_min),
        raw_store=FileRawStore(),
    )


def run_pipeline(
    keyword: str | None = None,
    *,
    seed: list[str] | None = None,
    limit_per_niche: int = 50,
) -> int:
    """Run a scrape pass. `seed` upserts those niches first (idempotent)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    weights = load_weights()
    print(f"radar v{__version__} — weights spec v{weights['version']}")

    cfg = Config.load()
    db = service_client(cfg)

    if seed:
        n = writers.seed_niches(db, seed, storefront=cfg.storefront)
        print(f"seeded {n} niches")

    itunes = _itunes_client(cfg)
    try:
        summary = run_scrape(db, itunes, limit_per_niche=limit_per_niche)
        # Score every niche off the snapshots just written, reusing the same client
        # (autocomplete depth probe) so demand picks up the proxy signal.
        scores = score_all_niches(db, itunes)
    finally:
        itunes.close()

    print(f"run {summary['run_id']}: {summary['status']} — {summary['notes']}")
    print(f"scored {len(scores)} niches (top: {scores[0]['keyword'] if scores else 'none'})")
    return 0
