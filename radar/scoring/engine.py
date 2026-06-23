"""Scoring engine (M3.6–3.7) — inputs -> sub-scores -> gates -> opportunity.

Pure: no DB, no network. The pipeline (M5) feeds it rows pulled from Postgres and
persists the returned Score into `niche_scores`; the TS live probe (M7) mirrors this
exact logic from the shared weights.json. Gates run BEFORE the blend (PRD §4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from radar.adapters.models import AppMetadata
from radar.scoring import subscores
from radar.scoring.weights import load_weights

# Competition is a divisor; floor its [0,1] form so a near-empty niche can't explode
# opportunity to infinity.
COMPETITION_FLOOR = 0.1


@dataclass
class NicheInputs:
    """Everything the scorer needs for one niche at one point in time."""

    apps: list[AppMetadata]
    autocomplete_depth: int = 0
    google_volume: int | None = None
    complaint_density: float = 0.0  # 0..1, from LLM review clustering (M6); 0 until then
    grossing_app_ids: set[int] = field(default_factory=set)


@dataclass
class Score:
    demand: float
    competition: float
    gap: float
    monetization: float
    buildability: float
    opportunity: float
    momentum: float | None = None  # filled by M4 once >=2 snapshots exist
    gated_out: bool = False
    gate_reason: str | None = None
    raw_inputs: dict = field(default_factory=dict)


def check_gates(
    demand: float, monetization: float, buildability: float, weights: dict
) -> tuple[bool, str | None]:
    """Hard zeros (PRD §4). Returns (gated_out, reason)."""
    g = weights["gates"]
    if demand < g["min_demand"]:
        return True, f"demand {demand:.1f} < floor {g['min_demand']}"
    if g.get("require_monetization", True) and monetization <= 0:
        return True, "no provable monetization (no paid/sub/grossing incumbent)"
    if buildability < g["min_buildability_multiplier"]:
        return True, f"buildability {buildability:.2f} < floor {g['min_buildability_multiplier']}"
    return False, None


def score_niche(inputs: NicheInputs, weights: dict | None = None) -> Score:
    """Compute sub-scores, apply gates, then blend Opportunity."""
    w = weights or load_weights()

    freshness = w.get("freshness")
    demand = subscores.demand_score(
        inputs.apps,
        autocomplete_depth=inputs.autocomplete_depth,
        google_volume=inputs.google_volume,
        weights=w["demand"],
        freshness=freshness,
    )
    competition = subscores.competition_score(inputs.apps, weights=w["competition"])
    gap = subscores.gap_score(
        inputs.apps,
        complaint_density=inputs.complaint_density,
        weights=w["gap"],
        freshness=freshness,
    )
    monetization = subscores.monetization_score(
        inputs.apps, grossing_app_ids=inputs.grossing_app_ids, weights=w["monetization"]
    )
    buildability = subscores.buildability_multiplier(inputs.apps, weights=w["buildability"])

    avg_freshness = None
    if freshness and inputs.apps:
        now = datetime.now(timezone.utc)
        avg_freshness = sum(
            subscores.app_freshness(a.current_ver_date, now, weights=freshness) for a in inputs.apps
        ) / len(inputs.apps)

    raw = {
        "n_apps": len(inputs.apps),
        "total_ratings": sum(a.rating_count or 0 for a in inputs.apps),
        "avg_freshness": avg_freshness,
        "autocomplete_depth": inputs.autocomplete_depth,
        "google_volume": inputs.google_volume,
        "complaint_density": inputs.complaint_density,
        "sub_scores": {
            "demand": demand,
            "competition": competition,
            "gap": gap,
            "monetization": monetization,
            "buildability": buildability,
        },
    }

    gated, reason = check_gates(demand, monetization, buildability, w)
    if gated:
        return Score(
            demand=demand,
            competition=competition,
            gap=gap,
            monetization=monetization,
            buildability=buildability,
            opportunity=0.0,
            gated_out=True,
            gate_reason=reason,
            raw_inputs=raw,
        )

    # Blend on the [0,1] scale so the result lands cleanly in 0..100.
    d, g, m = demand / 100, gap / 100, monetization / 100
    c = max(competition / 100, COMPETITION_FLOOR)
    opportunity = min(100.0, (d * g * m) / c * buildability * 100)

    return Score(
        demand=demand,
        competition=competition,
        gap=gap,
        monetization=monetization,
        buildability=buildability,
        opportunity=opportunity,
        raw_inputs=raw,
    )
