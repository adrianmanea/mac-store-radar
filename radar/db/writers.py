"""DB writers (M2.4–2.7).

Thin, idempotent writes over a Supabase client. Each writer is duck-typed on the client
(`client.table(name).upsert(...).execute()`) so tests pass a fake client and assert the
payloads without a live DB or the supabase package.

Idempotency strategy: every insert is an upsert against the table's unique constraint,
so re-running a day's scrape never duplicates rows (TECH-PRD §4.3 "at most once/day").
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any, Protocol

# Supabase caps payload size; chunk large batches.
BATCH = 500


class TableQuery(Protocol):
    def upsert(self, rows: list[dict], **kw: Any) -> TableQuery: ...
    def insert(self, rows: list[dict] | dict, **kw: Any) -> TableQuery: ...
    def execute(self) -> Any: ...


class DBClient(Protocol):
    def table(self, name: str) -> TableQuery: ...


def _chunks(rows: Sequence[dict], size: int = BATCH) -> Iterator[list[dict]]:
    for i in range(0, len(rows), size):
        yield list(rows[i : i + size])


def upsert_apps(client: DBClient, rows: Sequence[dict]) -> int:
    """Upsert canonical app records (M2.4). Conflict on app_id updates metadata."""
    n = 0
    for batch in _chunks(rows):
        client.table("apps").upsert(batch, on_conflict="app_id").execute()
        n += len(batch)
    return n


def insert_snapshots(client: DBClient, rows: Sequence[dict]) -> int:
    """Insert daily snapshots (M2.4). Idempotent on (app_id, captured_at)."""
    n = 0
    for batch in _chunks(rows):
        client.table("app_snapshots").upsert(
            batch, on_conflict="app_id,captured_at", ignore_duplicates=True
        ).execute()
        n += len(batch)
    return n


def insert_niche_apps(client: DBClient, rows: Sequence[dict]) -> int:
    """Insert niche↔app membership with rank (M2.5). Idempotent on the composite PK."""
    n = 0
    for batch in _chunks(rows):
        client.table("niche_apps").upsert(
            batch, on_conflict="niche_id,app_id,captured_at", ignore_duplicates=True
        ).execute()
        n += len(batch)
    return n


def insert_reviews(client: DBClient, rows: Sequence[dict]) -> int:
    """Insert reviews (M2.6). Dedupe on (app_id, apple_review_id)."""
    n = 0
    for batch in _chunks(rows):
        client.table("reviews").upsert(
            batch, on_conflict="app_id,apple_review_id", ignore_duplicates=True
        ).execute()
        n += len(batch)
    return n


def seed_niches(client: DBClient, keywords: Sequence[str], *, storefront: str = "us") -> int:
    """Seed the niches table (M2.5). Idempotent on the unique keyword."""
    rows = [{"keyword": k, "display_name": k, "storefront": storefront} for k in keywords]
    if rows:
        client.table("niches").upsert(rows, on_conflict="keyword", ignore_duplicates=True).execute()
    return len(rows)


def insert_candidates(client: DBClient, keywords: Sequence[str], *, source: str) -> int:
    """Record new discovery candidates (M9). Idempotent on the keyword PK."""
    rows = [{"keyword": k, "source": source, "status": "new"} for k in keywords]
    if rows:
        client.table("niche_candidates").upsert(
            rows, on_conflict="keyword", ignore_duplicates=True
        ).execute()
    return len(rows)


def update_candidate(client: DBClient, keyword: str, **fields: Any) -> None:
    """Update a candidate's status/score after validation (M9)."""
    client.table("niche_candidates").update(fields).eq("keyword", keyword).execute()


def promote_candidate(client: DBClient, keyword: str, *, storefront: str = "us") -> None:
    """Promote a validated candidate into the watched niches table (M9 auto-promote)."""
    client.table("niches").upsert(
        {"keyword": keyword, "display_name": keyword, "storefront": storefront, "is_watched": True},
        on_conflict="keyword",
        ignore_duplicates=True,
    ).execute()


def existing_keywords(client: DBClient) -> set[str]:
    """All keywords already in niches + niche_candidates — the discovery avoid-list."""
    out: set[str] = set()
    for table in ("niches", "niche_candidates"):
        res = client.table(table).select("keyword").execute()
        out.update(r["keyword"] for r in (res.data or []))
    return out


def start_run(client: DBClient) -> int:
    """Open a scrape_runs row, return its id (M2.7)."""
    res = client.table("scrape_runs").insert({"status": "partial"}).execute()
    return res.data[0]["id"]


def finish_run(client: DBClient, run_id: int, **fields: Any) -> None:
    """Close a scrape_runs row with counts/status/notes (M2.7)."""
    client.table("scrape_runs").update(fields).eq("id", run_id).execute()
