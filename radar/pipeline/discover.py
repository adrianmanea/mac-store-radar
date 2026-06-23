"""Discovery pipeline (M9): generate -> validate -> score -> auto-promote.

Turns the tool from a hand-fed scorer into a self-feeding discovery engine. Claude
proposes arbitrage-shaped keywords; each is cheaply validated against iTunes + scored;
winners auto-promote into the watched niches table so the daily cron tracks them.

Budget-bounded per run (weights.discovery.daily_candidate_budget) to stay under the
iTunes rate ceiling. Reuses the same search/lookup/score path as the main pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from radar.adapters import lookup, search
from radar.adapters.client import ITunesClient
from radar.db import writers
from radar.llm.discover import generate_candidates
from radar.scoring.engine import NicheInputs, score_niche
from radar.scoring.weights import load_weights

log = logging.getLogger("radar.pipeline")


def run_discovery(db, itunes: ITunesClient, anthropic, *, weights: dict | None = None) -> dict:
    """Generate candidates, validate+score within budget, auto-promote winners."""
    w = weights or load_weights()
    cfg = w["discovery"]
    budget = cfg["daily_candidate_budget"]

    # 1. generate, excluding everything we already know about
    avoid = sorted(writers.existing_keywords(db))
    candidates = generate_candidates(anthropic, n=budget, avoid=avoid)
    writers.insert_candidates(db, candidates, source="llm")
    log.info("discovery: %d new candidates generated", len(candidates))

    promoted: list[str] = []
    rejected = 0
    now = datetime.now(timezone.utc).isoformat()

    # 2. validate + score each (capped by budget)
    for kw in candidates[:budget]:
        stubs = search.search(itunes, kw, limit=50)
        ids = [s.app_id for s in stubs]
        metas = lookup.lookup(itunes, ids) if ids else []
        score = score_niche(NicheInputs(apps=metas), w)

        promote = (
            not score.gated_out
            and len(metas) >= cfg["min_apps"]
            and score.opportunity >= cfg["min_opportunity_to_promote"]
        )
        if promote:
            writers.promote_candidate(db, kw)
            writers.update_candidate(
                db,
                kw,
                status="promoted",
                best_opportunity=score.opportunity,
                n_apps=len(metas),
                last_checked=now,
                reason=f"opp={score.opportunity:.1f} >= {cfg['min_opportunity_to_promote']}",
            )
            promoted.append(kw)
        else:
            rejected += 1
            reason = score.gate_reason or (
                f"opp={score.opportunity:.1f} < {cfg['min_opportunity_to_promote']}"
                if len(metas) >= cfg["min_apps"]
                else f"only {len(metas)} apps"
            )
            writers.update_candidate(
                db,
                kw,
                status="rejected",
                best_opportunity=score.opportunity,
                n_apps=len(metas),
                last_checked=now,
                reason=reason,
            )

    summary = {
        "generated": len(candidates),
        "validated": min(len(candidates), budget),
        "promoted": len(promoted),
        "rejected": rejected,
        "promoted_keywords": promoted,
    }
    log.info("discovery: promoted %d, rejected %d", len(promoted), rejected)
    return summary
