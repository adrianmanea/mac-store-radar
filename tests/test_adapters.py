"""Adapter parse tests against real captured fixtures (offline)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from radar.adapters import autocomplete, charts, lookup, reviews, search
from radar.adapters.client import ITunesClient
from radar.adapters.limiter import TokenBucket

FIX = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text())


def _client(handler):
    return ITunesClient(
        limiter=TokenBucket(per_minute=10_000_000, capacity=1000),
        transport=httpx.MockTransport(handler),
        sleep=lambda _s: None,
    )


# --- search ---------------------------------------------------------------


def test_search_parse_ranks_in_order():
    stubs = search.parse(_load("search_obsidian.json"))
    assert len(stubs) >= 1
    assert stubs[0].search_rank == 1
    assert all(s.app_id > 0 for s in stubs)
    assert [s.search_rank for s in stubs] == list(range(1, len(stubs) + 1))


def test_search_build_url():
    url = search.build_url("android transfer", country="us", limit=200)
    assert "entity=macSoftware" in url and "limit=200" in url


# --- lookup ---------------------------------------------------------------


def test_lookup_parse_fields():
    metas = lookup.parse(_load("lookup_batch.json"))
    assert len(metas) == 2
    m = metas[0]
    assert m.app_id > 0 and m.name
    assert m.rating_count is not None


def test_lookup_chunking():
    batches = list(lookup.chunk(range(0, 305), size=150))
    assert [len(b) for b in batches] == [150, 150, 5]


def test_lookup_dedupes_and_batches_calls():
    payload = _load("lookup_batch.json")
    seen_urls = []

    def handler(req):
        seen_urls.append(str(req.url))
        return httpx.Response(200, json=payload)

    c = _client(handler)
    # duplicate ids collapse to unique set -> single batch -> 1 call
    out = lookup.lookup(c, [1, 1, 2, 2, 3])
    assert len(seen_urls) == 1
    assert len(out) == 2  # fixture has 2 results regardless of requested ids


# --- reviews --------------------------------------------------------------


def test_reviews_empty_feed_returns_empty_not_error():
    assert reviews.parse_page(123, _load("reviews_empty.json")) == []


def test_reviews_stops_on_empty_page():
    c = _client(lambda req: httpx.Response(200, json=_load("reviews_empty.json")))
    assert reviews.reviews(c, 6720708363) == []
    assert c.stats.api_calls == 1  # bailed after first empty page


# --- charts ---------------------------------------------------------------


def test_charts_parse_topfree():
    entries = charts.parse("top-free", _load("charts_topfree.json"))
    assert len(entries) == 5
    assert entries[0].rank == 1 and entries[0].app_id > 0
    assert entries[0].chart == "top-free"


def test_charts_unknown_feed_raises():
    import pytest

    with pytest.raises(ValueError):
        charts.build_url("bogus")


# --- autocomplete ---------------------------------------------------------


def test_autocomplete_parses_plist():
    body = (
        b'<?xml version="1.0"?><!DOCTYPE plist><plist version="1.0"><dict>'
        b"<key>hints</key><array>"
        b"<dict><key>term</key><string>android file transfer</string></dict>"
        b"<dict><key>term</key><string>android messages</string></dict>"
        b"</array></dict></plist>"
    )
    ac = autocomplete.parse("android", body)
    assert ac.depth == 2
    assert "android file transfer" in ac.hints


def test_autocomplete_garbage_degrades_to_zero():
    ac = autocomplete.parse("x", b"not a plist")
    assert ac.depth == 0
