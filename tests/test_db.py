"""DB layer tests — pure row builders + writers against a fake client (offline)."""

from __future__ import annotations

from datetime import datetime, timezone

from radar.adapters.models import AppMetadata, ChartEntry, Review
from radar.db import rows, writers

NOW = datetime(2026, 6, 23, 6, 0, tzinfo=timezone.utc)


# --- row builders ---------------------------------------------------------


def _meta(**kw):
    base = dict(app_id=42, name="Test App", rating_count=1000, avg_rating=4.2, price=0.0)
    base.update(kw)
    return AppMetadata(**base)


def test_app_row_serializes_dates_and_bumps_last_seen():
    m = _meta(release_date=NOW)
    r = rows.app_row(m, captured_at=NOW)
    assert r["app_id"] == 42
    assert r["release_date"] == NOW.isoformat()
    assert r["last_seen"] == NOW.isoformat()
    assert "rating_count" not in r  # rating lives on the snapshot, not apps


def test_snapshot_row_carries_timeseries_fields():
    r = rows.snapshot_row(_meta(version="1.2.3"), captured_at=NOW, chart_rank=7)
    assert r == {
        "app_id": 42,
        "captured_at": NOW.isoformat(),
        "rating_count": 1000,
        "avg_rating": 4.2,
        "price": 0.0,
        "version": "1.2.3",
        "chart_rank": 7,
    }


def test_review_row():
    rv = Review(app_id=42, apple_review_id="r1", rating=2, title="bad", body="x", author="a")
    assert rows.review_row(rv)["apple_review_id"] == "r1"


def test_chart_rank_map():
    entries = [
        ChartEntry(app_id=1, name="a", rank=1, chart="top-free"),
        ChartEntry(app_id=2, name="b", rank=2, chart="top-free"),
    ]
    assert rows.chart_rank_map(entries) == {1: 1, 2: 2}


# --- writers (fake client) ------------------------------------------------


class FakeQuery:
    def __init__(self, log, table):
        self.log = log
        self.table = table

    def upsert(self, rows, **kw):
        self.log.append(("upsert", self.table, len(rows), kw))
        return self

    def insert(self, row, **kw):
        self.log.append(("insert", self.table, row))
        return self

    def update(self, fields, **kw):
        self.log.append(("update", self.table, fields))
        return self

    def eq(self, *a, **kw):
        return self

    def execute(self):
        # mimic supabase returning inserted rows for start_run
        class R:
            data = [{"id": 99}]

        return R()


class FakeClient:
    def __init__(self):
        self.log = []

    def table(self, name):
        return FakeQuery(self.log, name)


def test_upsert_apps_chunks_and_uses_conflict():
    c = FakeClient()
    n = writers.upsert_apps(c, [{"app_id": i} for i in range(1200)])
    assert n == 1200
    calls = [x for x in c.log if x[0] == "upsert"]
    assert [x[2] for x in calls] == [500, 500, 200]  # chunked at 500
    assert calls[0][3]["on_conflict"] == "app_id"


def test_insert_snapshots_ignore_duplicates():
    c = FakeClient()
    writers.insert_snapshots(c, [{"app_id": 1, "captured_at": NOW.isoformat()}])
    op = c.log[0]
    assert op[1] == "app_snapshots"
    assert op[3]["ignore_duplicates"] is True
    assert op[3]["on_conflict"] == "app_id,captured_at"


def test_seed_niches_idempotent_payload():
    c = FakeClient()
    n = writers.seed_niches(c, ["a mac", "b mac"])
    assert n == 2
    assert c.log[0][3]["on_conflict"] == "keyword"


def test_start_and_finish_run():
    c = FakeClient()
    rid = writers.start_run(c)
    assert rid == 99
    writers.finish_run(c, rid, status="ok", apps_seen=10)
    assert ("update", "scrape_runs", {"status": "ok", "apps_seen": 10}) in c.log
