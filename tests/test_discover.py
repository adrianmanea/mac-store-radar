"""Discovery tests (M9) — LLM candidate parsing + the validate/promote funnel, offline."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from radar.adapters.client import ITunesClient
from radar.adapters.limiter import TokenBucket
from radar.llm import discover as llm_discover
from radar.pipeline.discover import run_discovery

FIX = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text())


# --- LLM candidate parsing ------------------------------------------------


class FakeResp:
    def __init__(self, text):
        self.content = [type("C", (), {"text": text})()]


class FakeAnthropic:
    def __init__(self, reply):
        self._reply = reply
        self.calls = []

    class _M:
        def __init__(self, outer):
            self.outer = outer

        def create(self, **kw):
            self.outer.calls.append(kw)
            return FakeResp(self.outer._reply)

    @property
    def messages(self):
        return FakeAnthropic._M(self)


def test_extract_json_array_plain():
    assert llm_discover._extract_json_array('["a mac", "b mac"]') == ["a mac", "b mac"]


def test_extract_json_array_fenced_with_prose():
    text = 'Here you go:\n```json\n["Heic To Jpg Mac", "RSS Reader Mac"]\n```'
    assert llm_discover._extract_json_array(text) == ["heic to jpg mac", "rss reader mac"]


def test_extract_json_array_garbage():
    assert llm_discover._extract_json_array("no array here") == []


def test_generate_candidates_dedupes_and_excludes_avoid():
    a = FakeAnthropic('["a mac", "a mac", "b mac", "tracked mac"]')
    out = llm_discover.generate_candidates(a, n=10, avoid=["tracked mac"])
    assert out == ["a mac", "b mac"]  # deduped + avoid excluded


# --- funnel ---------------------------------------------------------------


class FakeQuery:
    def __init__(self, db, table):
        self.db, self.table = db, table
        self._sel = False
        self._status = None

    def select(self, *a, **k):
        self._sel = True
        return self

    def eq(self, col, val, *a, **k):
        if col == "status":
            self._status = val
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def upsert(self, rows, **k):
        self.db.writes.append((self.table, "upsert", rows))
        if self.table == "niche_candidates":
            for r in rows:
                self.db.pool.setdefault(r["keyword"], "new")
        return self

    def update(self, fields, **k):
        self.db.writes.append((self.table, "update", fields))
        return self

    def execute(self):
        # pending_candidates: select keyword where status='new'
        if self._sel and self.table == "niche_candidates" and self._status == "new":
            data = [{"keyword": k} for k, s in self.db.pool.items() if s == "new"]
            return type("R", (), {"data": data})()
        return type("R", (), {"data": []})()


class FakeDB:
    def __init__(self):
        self.writes = []
        self.pool: dict[str, str] = {}

    def table(self, name):
        return FakeQuery(self, name)


def _itunes_returning(search_payload, lookup_payload):
    def handler(req):
        if "/search" in req.url.path:
            return httpx.Response(200, json=search_payload)
        return httpx.Response(200, json=lookup_payload)

    return ITunesClient(
        limiter=TokenBucket(per_minute=10_000_000, capacity=1000),
        transport=httpx.MockTransport(handler),
        sleep=lambda _s: None,
    )


WEIGHTS_MIN = {
    "discovery": {"min_opportunity_to_promote": 0.0, "min_apps": 1, "daily_candidate_budget": 5},
}


def test_run_discovery_validates_and_scores_without_promoting(monkeypatch):
    from radar.pipeline import discover as pipe

    class S:
        gated_out = False
        opportunity = 25.0
        gate_reason = None

    monkeypatch.setattr(pipe, "score_niche", lambda *a, **k: S())

    db = FakeDB()
    itunes = _itunes_returning(_load("search_obsidian.json"), _load("lookup_batch.json"))
    summary = run_discovery(
        db,
        itunes,
        ["new niche mac", "another niche mac"],
        weights={**_full_weights(), **WEIGHTS_MIN},
    )
    assert summary["generated"] == 2
    assert summary["validated"] == 2
    # the pool is scored as 'validated' — NOTHING enters the watch list
    assert any(
        t == "niche_candidates" and op == "update" and f.get("status") == "validated"
        for (t, op, f) in db.writes
    )
    assert not any(t == "niches" and op == "upsert" for (t, op, _r) in db.writes)


def test_run_discovery_rejects_thin_niches(monkeypatch):
    from radar.pipeline import discover as pipe

    class S:
        gated_out = True
        opportunity = 0.0
        gate_reason = "demand below floor"

    monkeypatch.setattr(pipe, "score_niche", lambda *a, **k: S())
    w = {**_full_weights(), **WEIGHTS_MIN}

    db = FakeDB()
    itunes = _itunes_returning(_load("search_obsidian.json"), _load("lookup_batch.json"))
    summary = run_discovery(db, itunes, ["weak niche mac"], weights=w)
    assert summary["validated"] == 0
    assert summary["rejected"] == 1
    assert any(
        t == "niche_candidates" and op == "update" and f.get("status") == "rejected"
        for (t, op, f) in db.writes
    )


# --- Google Suggest generator ---------------------------------------------

GOOGLE_BODY = (
    b'["android transfer mac",["android transfer mac","android transfer macos",'
    b'"best transfer tool","android file transfer mac app"],[],{}]'
)


def test_google_suggest_parse():
    from radar.adapters import google_suggest

    out = google_suggest.parse(GOOGLE_BODY)
    assert out[0] == "android transfer mac"
    assert "best transfer tool" in out


def test_google_suggest_parse_garbage():
    from radar.adapters import google_suggest

    assert google_suggest.parse(b"not json") == []


def test_google_candidates_filters_to_mac_and_excludes_avoid():
    from radar.pipeline.discover import google_candidates

    itunes = ITunesClient(
        limiter=TokenBucket(per_minute=10_000_000, capacity=1000),
        transport=httpx.MockTransport(lambda req: httpx.Response(200, content=GOOGLE_BODY)),
        sleep=lambda _s: None,
    )
    out = google_candidates(itunes, ["android transfer mac"], avoid={"android transfer mac"})
    # 'best transfer tool' dropped (no 'mac'); the seed itself dropped (in avoid)
    assert "best transfer tool" not in out
    assert "android transfer mac" not in out
    assert "android transfer macos" in out


def _full_weights():
    from radar.scoring.weights import load_weights

    return dict(load_weights())
