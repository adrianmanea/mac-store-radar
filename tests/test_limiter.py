"""Token-bucket tests with a fake clock — no real sleeping."""

from __future__ import annotations

from radar.adapters.limiter import TokenBucket


class FakeClock:
    """Controllable monotonic clock. sleep() advances virtual time."""

    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, secs: float) -> None:
        self.t += secs


def test_first_acquire_is_free_then_paces():
    clk = FakeClock()
    # capacity 1 -> steady pacing. 60/min = 1 token/sec.
    b = TokenBucket(per_minute=60, capacity=1, clock=clk.now, sleep=clk.sleep)
    assert b.acquire() == 0.0  # initial token available immediately
    waited = b.acquire()  # must wait ~1s for refill at 1 tok/s
    assert abs(waited - 1.0) < 1e-9
    assert abs(clk.t - 1.0) < 1e-9


def test_burst_capacity_then_clamp():
    clk = FakeClock()
    b = TokenBucket(per_minute=60, capacity=3, clock=clk.now, sleep=clk.sleep)
    # 3 immediate (burst), 4th waits one refill interval
    assert b.acquire() == 0.0
    assert b.acquire() == 0.0
    assert b.acquire() == 0.0
    assert abs(b.acquire() - 1.0) < 1e-9


def test_rate_is_respected_over_many_calls():
    clk = FakeClock()
    b = TokenBucket(per_minute=18, capacity=1, clock=clk.now, sleep=clk.sleep)
    for _ in range(19):
        b.acquire()
    # 18/min => 1 token / (60/18)s. 19 calls = 1 free + 18 paced intervals.
    expected = 18 * (60.0 / 18.0)
    assert abs(clk.t - expected) < 1e-6
