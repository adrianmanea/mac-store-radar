"""Discovery pipeline (M9): generate -> validate -> score -> auto-promote.

Turns the tool from a hand-fed scorer into a self-feeding discovery engine. Candidate
keywords come from one or more generators (Google Suggest — free/no-key; Claude — needs
key); each is cheaply validated against iTunes + scored; winners auto-promote into the
watched niches table so the daily cron tracks them.

The funnel (`run_discovery`) is source-agnostic — it takes a ready candidate list, so new
generators plug in without touching it. Budget-bounded per run to stay under the rate
ceiling.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from radar.adapters import google_suggest, lookup, search
from radar.adapters.client import ITunesClient
from radar.db import writers
from radar.scoring.engine import NicheInputs, score_niche
from radar.scoring.weights import load_weights

log = logging.getLogger("radar.pipeline")


def google_candidates(
    client: ITunesClient,
    seeds: list[str],
    *,
    avoid: set[str] | None = None,
    require_token: str | None = "mac",
) -> list[str]:
    """Expand seed prefixes into real high-volume queries via Google Suggest (no key).

    Keeps suggestions containing `require_token` (default 'mac') so we stay on Mac-niche
    intent, dedupes, and drops anything already tracked.
    """
    avoid = {a.lower() for a in (avoid or set())}
    seen: dict[str, None] = {}
    for seed in seeds:
        for s in google_suggest.suggest(client, seed):
            kw = s.lower().strip()
            if require_token and require_token not in kw:
                continue
            if kw and kw not in avoid:
                seen.setdefault(kw, None)
    log.info("discovery: %d google candidates from %d seeds", len(seen), len(seeds))
    return list(seen)


def run_discovery(
    db, itunes: ITunesClient, candidates: list[str], *, weights: dict | None = None
) -> dict:
    """Validate + score candidates (budget-capped), auto-promote winners. Source-agnostic."""
    w = weights or load_weights()
    cfg = w["discovery"]
    budget = cfg["daily_candidate_budget"]

    writers.insert_candidates(db, candidates, source="suggest")
    now = datetime.now(timezone.utc).isoformat()
    promoted: list[str] = []
    rejected = 0

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
