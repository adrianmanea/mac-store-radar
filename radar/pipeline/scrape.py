"""Scrape orchestrator (M5.1 — first pass).

Wires the M1 adapters to the M2 writers: resolve watched niches -> search -> dedupe ->
batched lookup -> upsert apps + insert snapshots + niche_apps -> run record. Review
fetch (M5.2), scoring (M4.5/5), and the LLM jobs (M6) layer on top of this spine.

Pure orchestration over injected clients, so it's exercised against a fake DB + mocked
iTunes transport in tests, and against the real services from `radar.run`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from radar.adapters import lookup, search
from radar.adapters.client import ITunesClient
from radar.adapters.errors import RateLimitError
from radar.db import rows, writers

log = logging.getLogger("radar.pipeline")


def _watched_niches(db) -> list[dict]:
    res = db.table("niches").select("id,keyword,storefront").eq("is_watched", True).execute()
    return res.data or []


def run_scrape(
    db,
    itunes: ITunesClient,
    *,
    captured_at: datetime | None = None,
    limit_per_niche: int = 50,
) -> dict:
    """Run one scrape pass over all watched niches. Returns the run summary dict."""
    captured_at = captured_at or datetime.now(timezone.utc)
    run_id = writers.start_run(db)

    niches = _watched_niches(db)
    log.info("scraping %d watched niches", len(niches))

    status = "ok"
    note = ""
    apps_written = 0
    id_union: dict[int, None] = {}
    try:
        # 4.1 search each niche -> collect membership + the union of app ids
        niche_app_rows: list[dict] = []
        for n in niches:
            stubs = search.search(
                itunes, n["keyword"], country=n.get("storefront") or "us", limit=limit_per_niche
            )
            for s in stubs:
                id_union.setdefault(s.app_id, None)
                niche_app_rows.append(
                    rows.niche_app_row(n["id"], s.app_id, s.search_rank, captured_at=captured_at)
                )

        # 4.3 batched lookup over the deduped union -> app + snapshot rows
        metas = lookup.lookup(itunes, id_union.keys())
        app_rows = [rows.app_row(m, captured_at=captured_at) for m in metas]
        snapshot_rows = [rows.snapshot_row(m, captured_at=captured_at) for m in metas]

        apps_written = writers.upsert_apps(db, app_rows)
        writers.insert_snapshots(db, snapshot_rows)
        writers.insert_niche_apps(db, niche_app_rows)
    except RateLimitError as exc:
        # The ceiling won — record a partial run and let the next day's rotation
        # self-heal (PRD §9). Don't crash the daily job over a transient limit.
        status = "partial"
        note = f"rate-limited: {exc}; "
        log.warning("scrape hit rate limit; marking run partial")

    notes = f"{note}niches={len(niches)} unique_apps={len(id_union)} retries={itunes.stats.retries}"
    summary = {
        "status": status,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "apps_seen": apps_written,
        "api_calls": itunes.stats.api_calls,
        "http_403s": itunes.stats.http_403s,
        "notes": notes,
    }
    writers.finish_run(db, run_id, **summary)
    log.info("scrape %s: %s", status, summary["notes"])
    return {"run_id": run_id, **summary}
