"""Candidate dedup (M9.5) — collapse niches that resolve to the same competitive set.

Different wordings ("whatsapp mac", "whatsapp macos", "whatsapp macbook") return the same
apps — they're one niche, not three. Keyword-string similarity misses this (the tokens
differ); the truth is the overlap of the returned app-ids. So we cluster validated
candidates by Jaccard over their `app_ids` and keep the highest-Opportunity representative
per cluster, marking the rest `duplicate` (the UI pool filters those out).

Pure clustering is unit-tested; the live entrypoint backfills any missing app-sets with a
single search each.
"""

from __future__ import annotations

import logging

from radar.adapters import search
from radar.adapters.client import ITunesClient
from radar.db import writers

log = logging.getLogger("radar.pipeline")


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a | b) else 0.0


def cluster_duplicates(
    candidates: list[dict], *, threshold: float = 0.6
) -> list[tuple[str, list[str]]]:
    """Greedy single-link clustering by app-set Jaccard.

    `candidates`: dicts with keys keyword, best_opportunity, app_ids (list[int]).
    Returns (keeper_keyword, [duplicate_keywords]) per cluster that has duplicates.
    Keeper = highest best_opportunity in the cluster.
    """
    # strongest first so the keeper tends to be the best-scoring niche
    ordered = sorted(candidates, key=lambda c: (c.get("best_opportunity") or 0), reverse=True)
    sets = {c["keyword"]: set(c.get("app_ids") or []) for c in ordered}

    assigned: set[str] = set()
    out: list[tuple[str, list[str]]] = []
    for c in ordered:
        kw = c["keyword"]
        if kw in assigned or not sets[kw]:
            continue
        dupes = []
        for other in ordered:
            okw = other["keyword"]
            if okw == kw or okw in assigned or not sets[okw]:
                continue
            if jaccard(sets[kw], sets[okw]) >= threshold:
                dupes.append(okw)
                assigned.add(okw)
        assigned.add(kw)
        if dupes:
            out.append((kw, dupes))
    return out


def _validated_candidates(db) -> list[dict]:
    res = (
        db.table("niche_candidates")
        .select("keyword,best_opportunity,app_ids")
        .eq("status", "validated")
        .execute()
    )
    return res.data or []


def run_dedup(db, itunes: ITunesClient, *, threshold: float = 0.6) -> dict:
    """Backfill missing app-sets, cluster, mark duplicates. Returns counts."""
    rows = _validated_candidates(db)

    # backfill app_ids for any validated candidate missing them (one search each)
    backfilled = 0
    for r in rows:
        if not r.get("app_ids"):
            ids = [s.app_id for s in search.search(itunes, r["keyword"], limit=50)][:30]
            r["app_ids"] = ids
            writers.update_candidate(db, r["keyword"], app_ids=ids)
            backfilled += 1

    clusters = cluster_duplicates(rows, threshold=threshold)
    duped = 0
    for keeper, dupes in clusters:
        for kw in dupes:
            writers.update_candidate(db, kw, status="duplicate", reason=f"dup of {keeper!r}")
            duped += 1

    log.info(
        "dedup: %d clusters, %d duplicates marked (backfilled %d)", len(clusters), duped, backfilled
    )
    return {"clusters": len(clusters), "duplicates": duped, "backfilled": backfilled}
