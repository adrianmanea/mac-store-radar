"""Sub-score functions (M3.1–3.5) — each pure, each normalized 0–100.

Higher = "more of that dimension": more demand, MORE competition (it's a divisor),
bigger gap, stronger monetization. Buildability is the exception — it returns a
multiplier (~0.4–1.0), not a 0–100 score.

The blend *weights* live in weights.json (tunable config). The *normalization caps*
below (REF_*) are calibration knobs too — tuned in M3.8 against the gut-check niche set.
They are deliberately explicit constants, not magic numbers buried in expressions.
"""

from __future__ import annotations

import math
from collections import Counter

from radar.adapters.models import AppMetadata

# --- normalization references (M3.8 calibration knobs) --------------------
REF_LOG_RATINGS = 6.0  # log10(1e6) total niche ratings -> demand saturates at 100
REF_AUTOCOMPLETE_DEPTH = 10  # this many hints -> full autocomplete signal
REF_LOG_GOOGLE_VOL = 6.0
REF_COMPETITOR_COUNT = 10  # this many incumbents above the floor -> full count signal
REF_PRICE_POINT = 20.0  # $ at which price-point signal saturates
REF_LOG_GAP = 6.0  # log10 of the unhappy-user mass -> gap saturates at 100


def _clamp100(x: float) -> float:
    return max(0.0, min(100.0, x))


def _renormalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return weights
    return {k: v / total for k, v in weights.items()}


def demand_score(
    apps: list[AppMetadata],
    *,
    autocomplete_depth: int = 0,
    google_volume: int | None = None,
    weights: dict,
) -> float:
    """log(total ratings) + autocomplete depth + (optional) google volume."""
    total_ratings = sum(a.rating_count or 0 for a in apps)
    ratings_c = _clamp100(math.log10(1 + total_ratings) / REF_LOG_RATINGS * 100)
    auto_c = _clamp100(autocomplete_depth / REF_AUTOCOMPLETE_DEPTH * 100)

    w = {
        "log_ratings_weight": weights["log_ratings_weight"],
        "autocomplete_depth_weight": weights["autocomplete_depth_weight"],
    }
    components = {"log_ratings_weight": ratings_c, "autocomplete_depth_weight": auto_c}
    if google_volume is not None:
        w["google_volume_weight"] = weights["google_volume_weight"]
        components["google_volume_weight"] = _clamp100(
            math.log10(1 + google_volume) / REF_LOG_GOOGLE_VOL * 100
        )
    w = _renormalize(w)  # drop google weight cleanly when absent
    return _clamp100(sum(components[k] * w[k] for k in w))


def competition_score(apps: list[AppMetadata], *, weights: dict) -> float:
    """count above floor + concentration (HHI) + incumbent quality. Higher = harder."""
    floor = weights["rating_floor"]
    incumbents = [a for a in apps if (a.rating_count or 0) >= floor]
    count_c = _clamp100(len(incumbents) / REF_COMPETITOR_COUNT * 100)

    total = sum(a.rating_count or 0 for a in incumbents)
    if total > 0:
        hhi = sum(((a.rating_count or 0) / total) ** 2 for a in incumbents)  # 0..1
    else:
        hhi = 0.0
    concentration_c = _clamp100(hhi * 100)

    if incumbents:
        avg_q = sum(a.avg_rating or 0 for a in incumbents) / len(incumbents)
    else:
        avg_q = 0.0
    quality_c = _clamp100(avg_q / 5.0 * 100)

    return _clamp100(
        count_c * weights["count_weight"]
        + concentration_c * weights["concentration_weight"]
        + quality_c * weights["incumbent_quality_weight"]
    )


def gap_score(apps: list[AppMetadata], *, complaint_density: float = 0.0, weights: dict) -> float:
    """high_volume × low_avg_rating (the money signal) + complaint density (LLM, M6).

    Per PRD the thesis is "a high-traffic app with lots of 2-star reviews", so we take
    the single most-unhappy-mass incumbent, not the niche average.
    """
    unhappy_mass = max(
        ((a.rating_count or 0) * (5.0 - (a.avg_rating or 5.0)) / 5.0 for a in apps),
        default=0.0,
    )
    volume_c = _clamp100(math.log10(1 + unhappy_mass) / REF_LOG_GAP * 100)
    complaint_c = _clamp100(complaint_density * 100)  # density given as 0..1
    return _clamp100(
        volume_c * weights["volume_x_lowrating_weight"]
        + complaint_c * weights["complaint_density_weight"]
    )


def monetization_score(
    apps: list[AppMetadata], *, grossing_app_ids: set[int] | None = None, weights: dict
) -> float:
    """%paid/sub + price points + grossing presence (falls back to paid ratio for Mac)."""
    grossing_app_ids = grossing_app_ids or set()
    if not apps:
        return 0.0

    def is_paid(a: AppMetadata) -> bool:
        return bool(a.is_subscription) or (a.price or 0) > 0

    paid = [a for a in apps if is_paid(a)]
    paid_ratio_c = _clamp100(len(paid) / len(apps) * 100)

    if paid:
        avg_price = sum(a.price or 0 for a in paid) / len(paid)
        price_c = _clamp100(min(avg_price / REF_PRICE_POINT, 1.0) * 100)
    else:
        price_c = 0.0

    grossing_c = _clamp100(sum(1 for a in apps if a.app_id in grossing_app_ids) / len(apps) * 100)

    return _clamp100(
        paid_ratio_c * weights["paid_sub_ratio_weight"]
        + price_c * weights["price_point_weight"]
        + grossing_c * weights["grossing_presence_weight"]
    )


def buildability_multiplier(apps: list[AppMetadata], *, weights: dict) -> float:
    """Multiplier from incumbents' LLM complexity class. Untagged -> neutral default.

    Uses the most common class among tagged incumbents as the niche's representative
    complexity. Returns ~0.4–1.0.
    """
    classes = [a.complexity_class for a in apps if a.complexity_class]
    if not classes:
        return float(weights["default_when_untagged"])
    most_common = Counter(classes).most_common(1)[0][0]
    table = weights["multiplier"]
    return float(table.get(most_common, weights["default_when_untagged"]))
