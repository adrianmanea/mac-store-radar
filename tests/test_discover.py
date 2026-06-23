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

    def select(self, *a, **k):
        self._sel = True
        return self

    def eq(self, *a, **k):
        return self

    def upsert(self, rows, **k):
        self.db.writes.append((self.table, "upsert", rows))
        return self

    def update(self, fields, **k):
        self.db.writes.append((self.table, "update", fields))
        return self

    def execute(self):
        if self._sel and self.table in ("niches", "niche_candidates"):
            return type("R", (), {"data": []})()  # nothing tracked yet -> empty avoid
        return type("R", (), {"data": []})()


class FakeDB:
    def __init__(self):
        self.writes = []

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


def test_run_discovery_promotes_when_above_threshold(monkeypatch):
    # force the engine to return a comfortably promotable score
    from radar.pipeline import discover as pipe

    class S:
        gated_out = False
        opportunity = 25.0
        gate_reason = None

    monkeypatch.setattr(pipe, "score_niche", lambda *a, **k: S())
    monkeypatch.setattr(pipe, "load_weights", lambda: {**_full_weights(), **WEIGHTS_MIN})

    db = FakeDB()
    itunes = _itunes_returning(_load("search_obsidian.json"), _load("lookup_batch.json"))
    anthropic = FakeAnthropic('["new niche mac", "another niche mac"]')

    summary = run_discovery(db, itunes, anthropic, weights={**_full_weights(), **WEIGHTS_MIN})
    assert summary["generated"] == 2
    assert summary["promoted"] == 2
    # each promotion upserts into niches
    assert any(t == "niches" and op == "upsert" for (t, op, _r) in db.writes)


def test_run_discovery_rejects_below_threshold(monkeypatch):
    from radar.pipeline import discover as pipe

    class S:
        gated_out = False
        opportunity = 1.0
        gate_reason = None

    monkeypatch.setattr(pipe, "score_niche", lambda *a, **k: S())
    w = {
        **_full_weights(),
        "discovery": {
            "min_opportunity_to_promote": 8.0,
            "min_apps": 1,
            "daily_candidate_budget": 5,
        },
    }

    db = FakeDB()
    itunes = _itunes_returning(_load("search_obsidian.json"), _load("lookup_batch.json"))
    anthropic = FakeAnthropic('["weak niche mac"]')
    summary = run_discovery(db, itunes, anthropic, weights=w)
    assert summary["promoted"] == 0
    assert summary["rejected"] == 1


def _full_weights():
    from radar.scoring.weights import load_weights

    return dict(load_weights())
