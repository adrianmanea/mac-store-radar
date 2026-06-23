"""Shared iTunes HTTP client (M1.1, M1.2, M1.8).

All adapters call through this one client so rate limiting, retry/backoff, raw
persistence, and call/403 counting happen in exactly one place. Tests inject an httpx
MockTransport for fully offline coverage.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from radar.adapters.errors import RateLimitError, TransientError
from radar.adapters.limiter import TokenBucket
from radar.adapters.rawstore import NullRawStore, RawStore

log = logging.getLogger("radar.adapters")

DEFAULT_UA = "mac-app-radar/0.1 (+https://github.com/adrian/mac-store-radar)"


@dataclass
class CallStats:
    """Per-client observability counters, surfaced into `scrape_runs` (M2.7)."""

    api_calls: int = 0
    http_403s: int = 0
    retries: int = 0
    transient_errors: int = 0


@dataclass
class ITunesClient:
    """Throttled, retrying GET client returning parsed JSON.

    Retries 403 (rate limit) and 5xx/timeout (transient) with exponential backoff,
    capped at `max_retries`. Persists every raw body to `raw_store` before returning.
    """

    limiter: TokenBucket = field(default_factory=TokenBucket)
    raw_store: RawStore = field(default_factory=NullRawStore)
    transport: httpx.BaseTransport | None = None
    timeout: float = 20.0
    max_retries: int = 4
    base_backoff: float = 1.0
    user_agent: str = DEFAULT_UA
    sleep: Callable[[float], None] = time.sleep
    stats: CallStats = field(default_factory=CallStats)

    def __post_init__(self) -> None:
        self._client = httpx.Client(
            timeout=self.timeout,
            transport=self.transport,
            headers={"User-Agent": self.user_agent},
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ITunesClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get_bytes(self, url: str) -> bytes:
        """GET `url` through the retry/limiter/persistence path, return the raw body.

        Used by adapters whose payload is not JSON (autocomplete returns plist XML).
        """
        resp = self._request(url)
        self.raw_store.put(url, resp.content, meta={"status": resp.status_code})
        return resp.content

    def get_json(self, url: str) -> dict:
        """GET `url`, persist raw, return parsed JSON. Raises AdapterError on give-up."""
        resp = self._request(url)
        self.raw_store.put(url, resp.content, meta={"status": resp.status_code})
        # iTunes occasionally serves JSON with a text/javascript content-type.
        return resp.json()

    def _request(self, url: str) -> httpx.Response:
        """Throttled GET with retry/backoff on 403 + 5xx + transport errors."""
        attempt = 0
        while True:
            self.limiter.acquire()
            self.stats.api_calls += 1
            try:
                resp = self._client.get(url)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                self.stats.transient_errors += 1
                if attempt >= self.max_retries:
                    raise TransientError(f"GET {url} failed after retries: {exc}") from exc
                self._backoff(attempt)
                attempt += 1
                continue

            if resp.status_code == 403:
                self.stats.http_403s += 1
                if attempt >= self.max_retries:
                    raise RateLimitError(f"GET {url} still 403 after {attempt} retries")
                log.warning("403 on %s — backing off (attempt %d)", url, attempt)
                self._backoff(attempt)
                attempt += 1
                continue

            if resp.status_code >= 500:
                self.stats.transient_errors += 1
                if attempt >= self.max_retries:
                    raise TransientError(f"GET {url} {resp.status_code} after retries")
                self._backoff(attempt)
                attempt += 1
                continue

            resp.raise_for_status()
            return resp

    def _backoff(self, attempt: int) -> None:
        self.stats.retries += 1
        self.sleep(self.base_backoff * (2**attempt))
