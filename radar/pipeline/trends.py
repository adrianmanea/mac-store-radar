"""Per-app trend computation (Trending).

Computes each app's rating velocity (Δratings/day) from its snapshot history and writes
it to apps.ratings_per_day, so the UI can rank "apps getting traffic now" with a cheap
ordered read. Velocity is meaningful only once >=2 daily snapshots exist per app — until
the cron accumulates day-over-day data, most values are ~0 (correctly: no movement yet).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from radar.scoring.momentum import app_velocity

log = logging.getLogger("radar.pipeline")

PAGE = 1000
BATCH = 500


def _paged(db, table: str, columns: str):
    """Yield all rows of a table, paginated past the 1000-row cap."""
    start = 0
    while True:
        res = db.table(table).select(columns).range(start, start + PAGE - 1).execute()
        rows = res.data or []
        yield from rows
        if len(rows) < PAGE:
            break
        start += PAGE


def _all_snapshots(db) -> dict[int, list[dict]]:
    """All snapshots grouped by app_id."""
    by_app: dict[int, list[dict]] = {}
    for r in _paged(db, "app_snapshots", "app_id,rating_count,captured_at"):
        by_app.setdefault(r["app_id"], []).append(r)
    return by_app


def compute_trends(db) -> dict:
    """Write ratings_per_day for every app with enough history. Returns counts.

    Uses the set_app_velocity RPC (bulk UPDATE) — partial upsert can't be used because
    its INSERT tuple violates apps.name NOT NULL. The UPDATE matches existing apps only,
    so a snapshot whose app row is missing is simply a no-op.
    """
    by_app = _all_snapshots(db)
    now = datetime.now(timezone.utc).isoformat()

    updates = []
    for app_id, snaps in by_app.items():
        v = app_velocity(snaps)
        if v is not None:
            updates.append({"app_id": app_id, "ratings_per_day": v, "trend_at": now})

    for i in range(0, len(updates), BATCH):
        db.rpc("set_app_velocity", {"updates": updates[i : i + BATCH]}).execute()

    log.info("trends: wrote velocity for %d/%d apps", len(updates), len(by_app))
    return {"apps_with_velocity": len(updates), "apps_total": len(by_app)}
