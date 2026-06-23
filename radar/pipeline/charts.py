"""Top-free chart ingestion (new-entrant discovery).

Niche search returns mature incumbents; trending/young apps surface on the charts.
This ingests the Mac top-free chart into apps + app_snapshots (with chart_rank), so
fresh entrants enter the catalog and start accumulating snapshots → measured velocity.
(Only top-free is reliable for Mac — paid/grossing feeds are empty; see adapters/charts.)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from radar.adapters import charts, lookup
from radar.adapters.client import ITunesClient
from radar.db import rows, writers

log = logging.getLogger("radar.pipeline")


def ingest_top_free(
    db, itunes: ITunesClient, *, limit: int = 100, captured_at: datetime | None = None
) -> dict:
    """Fetch the top-free Mac chart, upsert apps + snapshots stamped with chart_rank."""
    captured_at = captured_at or datetime.now(timezone.utc)
    entries = charts.charts(itunes, "top-free", limit=limit)
    rank_map = rows.chart_rank_map(entries)
    if not rank_map:
        log.warning("charts: top-free returned no entries")
        return {"apps": 0}

    metas = lookup.lookup(itunes, rank_map.keys())
    app_rows = [rows.app_row(m, captured_at=captured_at) for m in metas]
    snap_rows = [
        rows.snapshot_row(m, captured_at=captured_at, chart_rank=rank_map.get(m.app_id))
        for m in metas
    ]
    writers.upsert_apps(db, app_rows)
    writers.insert_snapshots(db, snap_rows)
    log.info("charts: ingested %d top-free apps", len(metas))
    return {"apps": len(metas)}
