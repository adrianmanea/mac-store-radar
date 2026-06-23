"""Scrape orchestrator test — fake DB + mocked iTunes transport, fully offline."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from radar.adapters.client import ITunesClient
from radar.adapters.limiter import TokenBucket
from radar.pipeline.scrape import run_scrape

FIX = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text())


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, db, table):
        self.db, self.table = db, table
        self._select_niches = False

    def select(self, *a, **k):
        self._select_niches = self.table == "niches"
        return self

    def eq(self, *a, **k):
        return self

    def upsert(self, rows, **kw):
        self.db.writes.append((self.table, "upsert", len(rows)))
        self._rows = rows
        return self

    def insert(self, row, **kw):
        self.db.writes.append((self.table, "insert", row))
        self._rows = [{"id": 1}]
        return self

    def update(self, fields, **kw):
        self.db.writes.append((self.table, "update", fields))
        self._rows = []
        return self

    def execute(self):
        if self._select_niches:
            return FakeResult(self.db.niches)
        return FakeResult(getattr(self, "_rows", []))


class FakeDB:
    def __init__(self, niches):
        self.niches = niches
        self.writes = []

    def table(self, name):
        return FakeQuery(self, name)


def _itunes():
    search_payload = _load("search_obsidian.json")
    lookup_payload = _load("lookup_batch.json")

    def handler(req):
        if "/search" in req.url.path:
            return httpx.Response(200, json=search_payload)
        return httpx.Response(200, json=lookup_payload)

    return ITunesClient(
        limiter=TokenBucket(per_minute=10_000_000, capacity=1000),
        transport=httpx.MockTransport(handler),
        sleep=lambda _s: None,
    )


def test_run_scrape_marks_partial_on_rate_limit():
    from radar.adapters.limiter import TokenBucket

    # Every request 403s -> client raises RateLimitError after retries.
    itunes = ITunesClient(
        limiter=TokenBucket(per_minute=10_000_000, capacity=1000),
        transport=httpx.MockTransport(lambda req: httpx.Response(403)),
        sleep=lambda _s: None,
        max_retries=1,
    )
    db = FakeDB(niches=[{"id": 1, "keyword": "obsidian", "storefront": "us"}])
    summary = run_scrape(db, itunes, limit_per_niche=10)

    assert summary["status"] == "partial"
    assert "rate-limited" in summary["notes"]
    # the run is still closed out (finish_run update), not left dangling
    assert ("scrape_runs", "update") in [(t, op) for (t, op, _x) in db.writes]


def test_run_scrape_writes_apps_snapshots_niche_apps_and_run():
    db = FakeDB(niches=[{"id": 1, "keyword": "obsidian", "storefront": "us"}])
    summary = run_scrape(db, _itunes(), limit_per_niche=10)

    tables_written = {w[0] for w in db.writes}
    assert {"apps", "app_snapshots", "niche_apps", "scrape_runs"} <= tables_written
    assert summary["status"] == "ok"
    assert summary["http_403s"] == 0
    # a scrape_runs row is opened (insert) and closed (update)
    ops = [(t, op) for (t, op, _x) in db.writes]
    assert ("scrape_runs", "insert") in ops
    assert ("scrape_runs", "update") in ops
