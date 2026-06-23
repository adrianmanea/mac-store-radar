"""ITunesClient tests — offline via httpx.MockTransport, fake sleep (no backoff wait)."""

from __future__ import annotations

import httpx
import pytest

from radar.adapters.client import ITunesClient
from radar.adapters.errors import RateLimitError, TransientError
from radar.adapters.limiter import TokenBucket


def _client(handler, **kw):
    # huge rate so the limiter never sleeps in tests; no-op sleep for backoff
    limiter = TokenBucket(per_minute=10_000_000, capacity=1000)
    return ITunesClient(
        limiter=limiter,
        transport=httpx.MockTransport(handler),
        sleep=lambda _s: None,
        base_backoff=0.0,
        **kw,
    )


def test_get_json_ok_and_counts():
    def handler(req):
        return httpx.Response(200, json={"ok": True})

    c = _client(handler)
    assert c.get_json("https://x/") == {"ok": True}
    assert c.stats.api_calls == 1
    assert c.stats.http_403s == 0


def test_403_then_success_retries():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(403)
        return httpx.Response(200, json={"ok": 1})

    c = _client(handler)
    assert c.get_json("https://x/") == {"ok": 1}
    assert c.stats.http_403s == 1
    assert c.stats.retries == 1
    assert c.stats.api_calls == 2


def test_persistent_403_raises_ratelimit():
    c = _client(lambda req: httpx.Response(403), max_retries=2)
    with pytest.raises(RateLimitError):
        c.get_json("https://x/")
    assert c.stats.http_403s == 3  # initial + 2 retries


def test_5xx_then_giveup_raises_transient():
    c = _client(lambda req: httpx.Response(503), max_retries=1)
    with pytest.raises(TransientError):
        c.get_json("https://x/")


def test_get_bytes_returns_raw_body():
    c = _client(lambda req: httpx.Response(200, content=b"<plist/>"))
    assert c.get_bytes("https://x/") == b"<plist/>"
