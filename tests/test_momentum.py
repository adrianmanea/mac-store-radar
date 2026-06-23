"""Momentum / velocity tests (M4) — pure functions over snapshot rows."""

from __future__ import annotations

from radar.scoring.momentum import app_velocity, niche_velocity, normalize_momentum


def snap(day, ratings):
    return {"captured_at": f"2026-06-{day:02d}T00:00:00+00:00", "rating_count": ratings}


def test_parse_handles_postgres_5digit_fraction():
    # Regression: Postgres timestamps have 5-digit fractional seconds, which break
    # datetime.fromisoformat on Python < 3.11 unless normalized.
    pts = [
        {"captured_at": "2026-06-23T16:24:28.32972+00:00", "rating_count": 1000},
        {"captured_at": "2026-06-25T16:24:28.32972+00:00", "rating_count": 1200},
    ]
    assert app_velocity(pts) == 100.0  # +200 over 2 days


def test_app_velocity_ratings_per_day():
    # +100 ratings over 2 days -> 50/day
    assert app_velocity([snap(1, 1000), snap(3, 1100)]) == 50.0


def test_app_velocity_uses_two_most_recent():
    v = app_velocity([snap(1, 0), snap(2, 10), snap(4, 110)])  # last pair: +100 / 2d
    assert v == 50.0


def test_app_velocity_needs_two_points():
    assert app_velocity([snap(1, 1000)]) is None
    assert app_velocity([]) is None


def test_app_velocity_zero_gap_returns_none():
    assert app_velocity([snap(1, 1000), snap(1, 1100)]) is None


def test_app_velocity_negative_delta_kept():
    # Apple recount can drop the total; velocity legitimately negative.
    assert app_velocity([snap(1, 1100), snap(3, 1000)]) == -50.0


def test_niche_velocity_averages_apps_with_history():
    by_app = {
        1: [snap(1, 0), snap(2, 100)],  # 100/day
        2: [snap(1, 0), snap(2, 200)],  # 200/day
        3: [snap(1, 500)],  # no history -> ignored
    }
    assert niche_velocity(by_app) == 150.0


def test_niche_velocity_none_when_no_history():
    assert niche_velocity({1: [snap(1, 5)]}) is None
    assert niche_velocity({}) is None


def test_normalize_minmax_across_niches():
    out = normalize_momentum({1: 10.0, 2: 110.0, 3: 60.0})
    assert out[1] == 0.0
    assert out[2] == 100.0
    assert out[3] == 50.0


def test_normalize_preserves_none_and_neutral_on_tie():
    out = normalize_momentum({1: 5.0, 2: 5.0, 3: None})
    assert out[1] == 50.0 and out[2] == 50.0  # all-equal -> neutral 50
    assert out[3] is None  # insufficient history stays None


def test_normalize_all_none():
    assert normalize_momentum({1: None, 2: None}) == {1: None, 2: None}
