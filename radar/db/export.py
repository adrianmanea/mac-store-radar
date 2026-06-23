"""Database export / backup (data backup).

The durable record is Supabase Postgres (the Supabase free tier has no guaranteed
automated backups). This dumps every table to newline-delimited JSON so the collected
data — snapshots, scores, candidates — survives a project loss and is re-importable.

Used by `radar --export DIR`; a weekly GitHub Action uploads the output as an artifact.
Paginates because Supabase caps a select at 1000 rows.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("radar.db")

TABLES = [
    "apps",
    "app_snapshots",
    "niches",
    "niche_apps",
    "niche_scores",
    "reviews",
    "unmet_needs",
    "demand_signals",
    "scrape_runs",
    "niche_candidates",
]

PAGE = 1000


def _dump_table(db, table: str, path: Path) -> int:
    """Stream a table to {table}.jsonl, paginating. Returns row count."""
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        start = 0
        while True:
            res = db.table(table).select("*").range(start, start + PAGE - 1).execute()
            rows = res.data or []
            for row in rows:
                fh.write(json.dumps(row, default=str) + "\n")
            n += len(rows)
            if len(rows) < PAGE:
                break
            start += PAGE
    return n


def export_all(db, out_dir: str | Path) -> dict:
    """Export every table to `out_dir`/<table>.jsonl + a manifest.json. Returns counts."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for t in TABLES:
        counts[t] = _dump_table(db, t, out / f"{t}.jsonl")
        log.info("exported %s: %d rows", t, counts[t])
    manifest = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "tables": counts,
        "total_rows": sum(counts.values()),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
