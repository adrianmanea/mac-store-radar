"""Scoring engine tests (M3) — pure, weights from the real shared spec."""

from __future__ import annotations

from radar.adapters.models import AppMetadata
from radar.scoring import subscores
from radar.scoring.engine import NicheInputs, score_niche
from radar.scoring.weights import load_weights

W = load_weights()


def app(app_id=1, ratings=1000, avg=4.0, price=0.0, sub=False, cclass=None):
    return AppMetadata(
        app_id=app_id,
        name=f"App{app_id}",
        rating_count=ratings,
        avg_rating=avg,
        price=price,
        is_subscription=sub,
        complexity_class=cclass,
    )


# --- sub-scores -----------------------------------------------------------


def test_demand_rises_with_ratings():
    lo = subscores.demand_score([app(ratings=10)], weights=W["demand"])
    hi = subscores.demand_score([app(ratings=500_000)], weights=W["demand"])
    assert 0 <= lo < hi <= 100


def test_demand_renormalizes_without_google():
    # absent google volume must not depress the score vs present-but-zero handling
    s = subscores.demand_score([app(ratings=1000)], autocomplete_depth=5, weights=W["demand"])
    assert 0 < s <= 100


def test_competition_higher_with_more_strong_incumbents():
    weak = subscores.competition_score([app(ratings=10, avg=3.0)], weights=W["competition"])
    strong = subscores.competition_score(
        [app(i, ratings=50_000, avg=4.8) for i in range(10)], weights=W["competition"]
    )
    assert strong > weak


def test_gap_picks_unhappy_high_volume_incumbent():
    happy = subscores.gap_score([app(ratings=100_000, avg=4.9)], weights=W["gap"])
    unhappy = subscores.gap_score([app(ratings=100_000, avg=2.0)], weights=W["gap"])
    assert unhappy > happy


def test_monetization_zero_when_all_free():
    assert subscores.monetization_score([app(price=0.0)], weights=W["monetization"]) == 0.0
    paid = subscores.monetization_score(
        [app(price=9.99), app(app_id=2, sub=True)], weights=W["monetization"]
    )
    assert paid > 0


def test_buildability_default_and_table():
    assert subscores.buildability_multiplier([app()], weights=W["buildability"]) == 1.0
    native = subscores.buildability_multiplier(
        [app(cclass="native_complex")], weights=W["buildability"]
    )
    assert native == W["buildability"]["multiplier"]["native_complex"]


# --- gates ----------------------------------------------------------------


def test_gate_no_monetization_zeros_opportunity():
    s = score_niche(NicheInputs(apps=[app(ratings=500_000, avg=2.0, price=0.0)]))
    assert s.gated_out is True
    assert s.opportunity == 0.0
    assert "monetization" in s.gate_reason


def test_gate_low_demand_zeros_opportunity():
    s = score_niche(NicheInputs(apps=[app(ratings=1, avg=2.0, price=9.99)]))
    assert s.gated_out is True
    assert "demand" in s.gate_reason


def test_gate_unbuildable_zeros_opportunity():
    s = score_niche(
        NicheInputs(
            apps=[app(ratings=500_000, avg=2.0, price=9.99, cclass="native_complex")],
            autocomplete_depth=10,
        )
    )
    # native_complex multiplier 0.4 < min 0.5 -> gated
    assert s.gated_out is True
    assert "buildability" in s.gate_reason


# --- blend ----------------------------------------------------------------


def test_full_opportunity_in_range_and_traceable():
    s = score_niche(
        NicheInputs(
            apps=[
                app(1, ratings=200_000, avg=2.3, price=9.99, cclass="wrapper"),
                app(2, ratings=5_000, avg=2.8, price=4.99, cclass="wrapper"),
            ],
            autocomplete_depth=8,
        )
    )
    assert s.gated_out is False
    assert 0 < s.opportunity <= 100
    assert s.raw_inputs["sub_scores"]["demand"] > 0
    assert s.raw_inputs["total_ratings"] == 205_000


def test_weak_competition_beats_strong_competition_same_demand():
    common = dict(ratings=100_000, avg=2.2, price=9.99, cclass="wrapper")
    weak = score_niche(NicheInputs(apps=[app(**common)], autocomplete_depth=8))
    strong = score_niche(
        NicheInputs(
            apps=[app(**common)]
            + [app(i, ratings=80_000, avg=4.7, price=9.99) for i in range(2, 12)],
            autocomplete_depth=8,
        )
    )
    assert weak.opportunity > strong.opportunity
