"""Score computation step (M4.5 / M5 §4.5).

Reads each niche's current apps + latest snapshot metrics from Postgres, runs the pure
scoring engine, and writes a `niche_scores` row. No API calls except an optional
autocomplete depth probe per niche (demand proxy); a failure there degrades to depth 0.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from radar.adapters.client import ITunesClient
from radar.adapters.errors import AdapterError
from radar.adapters.models import AppMetadata
from radar.scoring.engine import NicheInputs, score_niche
from radar.scoring.weights import load_weights

log = logging.getLogger("radar.pipeline")


def _latest_snapshot_by_app(db, app_ids: list[int]) -> dict[int, dict]:
    """Most-recent snapshot row per app_id (rating_count/avg_rating/price/version)."""
    if not app_ids:
        return {}
    res = (
        db.table("app_snapshots")
        .select("app_id,rating_count,avg_rating,price,version,captured_at")
        .in_("app_id", app_ids)
        .order("captured_at", desc=True)
        .execute()
    )
    out: dict[int, dict] = {}
    for row in res.data or []:
        out.setdefault(row["app_id"], row)  # first seen = latest due to desc order
    return out


def _niche_apps(db, niche_id: int) -> list[int]:
    res = (
        db.table("niche_apps")
        .select("app_id,captured_at")
        .eq("niche_id", niche_id)
        .order("captured_at", desc=True)
        .execute()
    )
    # take the most recent capture's membership
    rows = res.data or []
    if not rows:
        return []
    latest = rows[0]["captured_at"]
    return [r["app_id"] for r in rows if r["captured_at"] == latest]


def _build_metadata(db, app_ids: list[int]) -> list[AppMetadata]:
    if not app_ids:
        return []
    apps = (
        db.table("apps")
        .select("app_id,name,price,is_subscription,complexity_class")
        .in_("app_id", app_ids)
        .execute()
    ).data or []
    snaps = _latest_snapshot_by_app(db, app_ids)
    out = []
    for a in apps:
        snap = snaps.get(a["app_id"], {})
        out.append(
            AppMetadata(
                app_id=a["app_id"],
                name=a["name"],
                price=snap.get("price", a.get("price")),
                is_subscription=a.get("is_subscription"),
                complexity_class=a.get("complexity_class"),
                rating_count=snap.get("rating_count"),
                avg_rating=snap.get("avg_rating"),
            )
        )
    return out


def score_all_niches(
    db, itunes: ITunesClient | None = None, *, captured_at: datetime | None = None
) -> list[dict]:
    """Score every niche, persist niche_scores, return a sortable summary list."""
    captured_at = captured_at or datetime.now(timezone.utc)
    weights = load_weights()
    niches = (db.table("niches").select("id,keyword").execute()).data or []

    summaries: list[dict] = []
    for n in niches:
        app_ids = _niche_apps(db, n["id"])
        apps = _build_metadata(db, app_ids)

        depth = 0
        if itunes is not None:
            try:
                from radar.adapters.autocomplete import autocomplete

                depth = autocomplete(itunes, n["keyword"]).depth
            except AdapterError as exc:  # unofficial endpoint — degrade, never abort
                log.warning("autocomplete failed for %s: %s", n["keyword"], exc)

        score = score_niche(NicheInputs(apps=apps, autocomplete_depth=depth), weights)
        db.table("niche_scores").upsert(
            {
                "niche_id": n["id"],
                "captured_at": captured_at.isoformat(),
                "demand": score.demand,
                "competition": score.competition,
                "gap": score.gap,
                "monetization": score.monetization,
                "buildability": score.buildability,
                "opportunity": score.opportunity,
                "momentum": score.momentum,
                "gated_out": score.gated_out,
                "gate_reason": score.gate_reason,
                "raw_inputs": score.raw_inputs,
            },
            on_conflict="niche_id,captured_at",
        ).execute()

        summaries.append(
            {
                "keyword": n["keyword"],
                "n_apps": len(apps),
                "opportunity": round(score.opportunity, 1),
                "demand": round(score.demand, 1),
                "competition": round(score.competition, 1),
                "gap": round(score.gap, 1),
                "monetization": round(score.monetization, 1),
                "gated_out": score.gated_out,
                "gate_reason": score.gate_reason,
            }
        )

    summaries.sort(key=lambda s: s["opportunity"], reverse=True)
    return summaries
