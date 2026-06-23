"""Momentum / velocity (M4) — the one signal manual research can't give.

Pure functions over snapshot rows (TECH-PRD §2 window query, expressed in Python so it's
unit-testable and shares the engine's normalization style). Momentum is normalized
*across niches* (a niche is only "hot" relative to the others), so it's computed as a
post-pass over all niches, not inside the per-niche scorer.
"""

from __future__ import annotations

import re
from datetime import datetime

# A snapshot row here is a dict with at least: captured_at (iso str), rating_count (int).

# Postgres returns variable-length fractional seconds (e.g. .32972); pad/truncate to the
# 6 digits that datetime.fromisoformat requires on Python < 3.11.
_FRACTION = re.compile(r"\.(\d+)")


def _parse(ts: str | datetime) -> datetime:
    if isinstance(ts, datetime):
        return ts
    ts = ts.replace("Z", "+00:00")
    ts = _FRACTION.sub(lambda m: "." + (m.group(1) + "000000")[:6], ts)
    return datetime.fromisoformat(ts)


def app_velocity(snapshots: list[dict]) -> float | None:
    """Ratings/day for one app from its two most recent snapshots.

    Returns None when there's <2 points or a zero/negative time gap (can't infer rate).
    Rating count is monotonic in practice; a negative delta (Apple recount) is kept as-is
    so it can legitimately drag a niche's momentum down.
    """
    pts = sorted(
        (s for s in snapshots if s.get("rating_count") is not None),
        key=lambda s: _parse(s["captured_at"]),
    )
    if len(pts) < 2:
        return None
    a, b = pts[-2], pts[-1]
    days = (_parse(b["captured_at"]) - _parse(a["captured_at"])).total_seconds() / 86400.0
    if days <= 0:
        return None
    return (b["rating_count"] - a["rating_count"]) / days


def niche_velocity(snapshots_by_app: dict[int, list[dict]]) -> float | None:
    """Average per-app ratings/day across a niche. None when no app has 2 points yet."""
    rates = [v for v in (app_velocity(s) for s in snapshots_by_app.values()) if v is not None]
    if not rates:
        return None
    return sum(rates) / len(rates)


def normalize_momentum(raw_by_niche: dict[int, float | None]) -> dict[int, float | None]:
    """Min-max normalize raw niche velocities to 0–100 across the set.

    Niches without enough history (raw None) stay None. When every niche shares the same
    velocity (or only one has data), they map to 50 — neutral, not a false 0 or 100.
    """
    have = {k: v for k, v in raw_by_niche.items() if v is not None}
    out: dict[int, float | None] = {k: None for k in raw_by_niche}
    if not have:
        return out
    lo, hi = min(have.values()), max(have.values())
    span = hi - lo
    for k, v in have.items():
        out[k] = 50.0 if span == 0 else (v - lo) / span * 100.0
    return out
