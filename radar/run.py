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


def run_discovery_job() -> int:
    """Decoupled discovery job (M9): generate -> validate -> auto-promote.

    Google Suggest is the default generator (free, no key). If ANTHROPIC_API_KEY is set,
    Claude candidates are added on top. Either way, the funnel validates + scores + auto-
    promotes the winners.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from radar.db import writers
    from radar.pipeline.discover import google_candidates, harvest_prefixes, run_discovery
    from radar.seeds import GOOGLE_SEED_PREFIXES

    cfg = Config.load()
    db = service_client(cfg)
    itunes = _itunes_client(cfg)
    try:
        avoid = writers.existing_keywords(db)
        # Seed prefixes = the static hand-set list + prefixes harvested from the catalog
        # we've already scraped (self-bootstrapping; the more we scrape, the more it finds).
        seeds = list(dict.fromkeys(GOOGLE_SEED_PREFIXES + harvest_prefixes(db)))
        candidates = google_candidates(itunes, seeds, avoid=avoid)

        # LLM augmentation is best-effort: Google already produced candidates, so a
        # missing key / missing dependency / API error must not abort the run.
        if cfg.anthropic_api_key:
            try:
                from radar.llm.client import anthropic_client
                from radar.llm.discover import generate_candidates

                llm = generate_candidates(anthropic_client(cfg), n=30, avoid=sorted(avoid))
                merged: dict[str, None] = dict.fromkeys(candidates)
                for c in llm:
                    merged.setdefault(c, None)
                candidates = list(merged)
                print(f"discovery sources: google + llm -> {len(candidates)} candidates")
            except Exception as exc:  # noqa: BLE001 - augmentation only; degrade to google
                logging.warning("LLM augmentation failed (%s); continuing with google", exc)
                print(f"discovery source: google only (llm failed) -> {len(candidates)} candidates")
        else:
            print(f"discovery source: google only (no key) -> {len(candidates)} candidates")

        summary = run_discovery(db, itunes, candidates)
    finally:
        itunes.close()
    print(
        f"discovery: scored {summary['scored']} candidates "
        f"({summary['validated']} validated, {summary['rejected']} rejected). "
        f"Pool grows; nothing auto-tracked — pick with `radar --watch`."
    )
    return 0


def run_dedup_job() -> int:
    """Collapse candidate niches that resolve to the same competitive set (M9.5)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from radar.pipeline.dedup import run_dedup

    cfg = Config.load()
    db = service_client(cfg)
    itunes = _itunes_client(cfg)
    try:
        res = run_dedup(db, itunes)
    finally:
        itunes.close()
    print(
        f"dedup: {res['clusters']} clusters, marked {res['duplicates']} duplicates "
        f"(backfilled {res['backfilled']} app-sets)"
    )
    return 0


def run_watch(keywords: list[str]) -> int:
    """Promote hand-picked candidates into the watch list (the daily-tracked niches)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from radar.db import writers

    cfg = Config.load()
    db = service_client(cfg)
    for kw in keywords:
        writers.promote_candidate(db, kw, storefront=cfg.storefront)
        writers.update_candidate(db, kw, status="watched")
    print(f"now watching {len(keywords)} niche(s): {keywords}")
    return 0


def run_export(out_dir: str) -> int:
    """Export every table to JSONL for backup (no LLM/iTunes; just DB reads)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from radar.db.export import export_all

    cfg = Config.load()
    db = service_client(cfg)
    manifest = export_all(db, out_dir)
    n_tables = len(manifest["tables"])
    print(f"exported {manifest['total_rows']} rows across {n_tables} tables -> {out_dir}")
    return 0


def run_tagging(cap: int = 50) -> int:
    """Decoupled LLM job (M6.2): tag untagged apps with a buildability class.

    Separate from the scrape so a slow/expensive Claude call never blocks data
    collection. Requires ANTHROPIC_API_KEY.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from radar.llm.buildability import tag_untagged
    from radar.llm.client import anthropic_client

    cfg = Config.load()
    db = service_client(cfg)
    res = tag_untagged(db, anthropic_client(cfg), cap=cap)
    print(f"buildability: tagged {res['tagged']}/{res['seen']} apps")
    return 0
