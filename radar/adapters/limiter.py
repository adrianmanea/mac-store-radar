"""Token-bucket rate limiter (M1.1).

Global pace for all iTunes calls — default ~18 req/min (headroom below the empirical
~20/min ceiling, TECH-PRD §0). Clock is injectable so tests run with a fake clock and
no real sleeping.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class TokenBucket:
    """Classic token bucket. Thread-safe; refills continuously at `rate` tokens/sec.

    `acquire()` blocks until a token is available, then consumes one. With the default
    capacity of 1 this paces calls to a steady interval; a larger capacity allows short
    bursts before the steady rate clamps in.
    """

    def __init__(
        self,
        per_minute: float = 18.0,
        capacity: float | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if per_minute <= 0:
            raise ValueError("per_minute must be > 0")
        self.rate = per_minute / 60.0  # tokens per second
        self.capacity = float(capacity) if capacity is not None else 1.0
        self._tokens = self.capacity
        self._clock = clock
        self._sleep = sleep
        self._last = clock()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = self._clock()
        elapsed = now - self._last
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._last = now

    def acquire(self, tokens: float = 1.0) -> float:
        """Block until `tokens` are available, consume them, return seconds waited."""
        if tokens > self.capacity:
            raise ValueError("requested tokens exceed bucket capacity")
        # Epsilon guards against float drift: deficit/rate * rate can land a hair below
        # `tokens` (e.g. 0.99999...), which would otherwise busy-loop forever.
        eps = 1e-9
        waited = 0.0
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens - eps:
                    self._tokens = max(0.0, self._tokens - tokens)
                    return waited
                deficit = tokens - self._tokens
                wait = deficit / self.rate
            self._sleep(wait)
            waited += wait
