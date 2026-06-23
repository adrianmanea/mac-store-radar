"""Chart ingestion + per-app trend computation tests (offline)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from radar.adapters.client import ITunesClient
from radar.adapters.limiter import TokenBucket
from radar.pipeline.charts import ingest_top_free
from radar.pipeline.trends import compute_trends

FIX = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text())


# --- chart ingestion ------------------------------------------------------


class FakeQ:
    def __init__(self, db, table):
        self.db, self.table = db, table

    def upsert(self, rows, **k):
        self.db.writes.append((self.table, "upsert", len(rows)))
        return self

    def execute(self):
        return type("R", (), {"data": []})()


class FakeDB:
    def __init__(self):
        self.writes = []

    def table(self, name):
        return FakeQ(self, name)


def _itunes(chart_payload, lookup_payload):
    def handler(req):
        if "/rss/" in req.url.path:
            return httpx.Response(200, json=chart_payload)
        return httpx.Response(200, json=lookup_payload)

    return ITunesClient(
        limiter=TokenBucket(per_minute=10_000_000, capacity=1000),
        transport=httpx.MockTransport(handler),
        sleep=lambda _s: None,
    )


def test_ingest_top_free_upserts_apps_and_snapshots():
    db = FakeDB()
    itunes = _itunes(_load("charts_topfree.json"), _load("lookup_batch.json"))
    res = ingest_top_free(db, itunes, limit=5)
    assert res["apps"] == 2  # lookup fixture has 2
    tables = {w[0] for w in db.writes}
    assert "apps" in tables and "app_snapshots" in tables


# --- trend computation ----------------------------------------------------


class TrendQ:
    def __init__(self, db, table):
        self.db, self.table = db, table

    def select(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def upsert(self, rows, **k):
        self.db.upserts.extend(rows)
        return self

    def execute(self):
        start, _ = getattr(self, "_range", (0, 0))
        if self.table == "app_snapshots":
            return type("R", (), {"data": self.db.snaps if start == 0 else []})()
        return type("R", (), {"data": []})()


class TrendDB:
    def __init__(self, snaps):
        self.snaps = snaps
        self.upserts = []  # rows passed to the set_app_velocity RPC

    def table(self, name):
        return TrendQ(self, name)

    def rpc(self, fn, params):
        assert fn == "set_app_velocity"
        self.upserts.extend(params["updates"])
        return type("Q", (), {"execute": lambda self: None})()


def test_compute_trends_writes_velocity():
    snaps = [
        {"app_id": 1, "rating_count": 100, "captured_at": "2026-06-21T00:00:00+00:00"},
        {"app_id": 1, "rating_count": 300, "captured_at": "2026-06-23T00:00:00+00:00"},  # +100/day
        {
            "app_id": 2,
            "rating_count": 50,
            "captured_at": "2026-06-23T00:00:00+00:00",
        },  # 1 pt -> skip
    ]
    db = TrendDB(snaps)
    res = compute_trends(db)
    assert res["apps_with_velocity"] == 1
    assert res["apps_total"] == 2
    row = next(u for u in db.upserts if u["app_id"] == 1)
    assert row["ratings_per_day"] == 100.0
