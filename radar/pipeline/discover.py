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
import re
from collections import Counter
from datetime import datetime, timezone

from radar.adapters import google_suggest, lookup, search
from radar.adapters.client import ITunesClient
from radar.db import writers
from radar.scoring.engine import NicheInputs, score_niche
from radar.scoring.weights import load_weights

log = logging.getLogger("radar.pipeline")

# Generic / marketing words that aren't niche signals — dropped from harvested prefixes.
_STOP = {
    "your",
    "with",
    "that",
    "make",
    "free",
    "best",
    "easy",
    "tool",
    "tools",
    "apps",
    "mac",
    "macos",
    "macbook",
    "app",
    "pro",
    "plus",
    "lite",
    "edition",
    "studio",
    "manager",  # too generic alone; kept in bigrams
}
_WORD = re.compile(r"[a-z]{4,}")

# Google Suggest returns web-search phrasings that aren't how people search the App Store.
# Strip them before spending an iTunes call validating them.
_QUESTION_STARTS = {
    "how",
    "what",
    "where",
    "why",
    "when",
    "which",
    "who",
    "is",
    "are",
    "can",
    "does",
    "do",
    "will",
    "should",
}
_NOISE_TOKENS = {
    # web/community phrasings
    "reddit",
    "vs",
    "versus",
    "tutorial",
    "guide",
    "review",
    "reviews",
    "youtube",
    "quora",
    "wiki",
    "wikipedia",
    "meaning",
    "definition",
    # non-English (Google leaks localized completions)
    "kostenlos",
    "gratuit",
    "gratuita",
    "gratis",
    "descargar",
    "telecharger",
    "italiano",
    "espanol",
    "deutsch",
    "francais",
    "portugues",
}
MAX_WORDS = 6


def is_noisy(keyword: str) -> bool:
    """True if a candidate looks like a web query, not an App Store search term."""
    toks = keyword.lower().split()
    if not toks:
        return True
    if toks[0] in _QUESTION_STARTS:
        return True
    if len(toks) > MAX_WORDS:
        return True
    if any(t in _NOISE_TOKENS for t in toks):
        return True
    if not keyword.isascii():  # foreign-script completions
        return True
    return False


def prefixes_from_names(
    names: list[str], *, top_words: int = 20, top_bigrams: int = 15
) -> list[str]:
    """Extract candidate search prefixes from app titles (pure, testable).

    Frequent single words + bigrams that competitors put in their titles ARE the niche
    signals. Each becomes a '<term> mac' prefix for Google Suggest to expand.
    """
    words: Counter[str] = Counter()
    bigrams: Counter[str] = Counter()
    for name in names:
        toks = [t for t in _WORD.findall((name or "").lower())]
        meaningful = [t for t in toks if t not in _STOP]
        words.update(meaningful)
        for i in range(len(toks) - 1):
            a, b = toks[i], toks[i + 1]
            if a not in _STOP and b not in _STOP:
                bigrams.update([f"{a} {b}"])

    prefixes: list[str] = []
    for term, _ in words.most_common(top_words):
        prefixes.append(f"{term} mac")
    for bg, _ in bigrams.most_common(top_bigrams):
        prefixes.append(f"{bg} mac")

    # de-dup, preserve order
    return list(dict.fromkeys(prefixes))


def harvest_prefixes(db, *, limit: int = 2000) -> list[str]:
    """Read scraped app titles and derive seed prefixes (catalog-harvest generator)."""
    res = db.table("apps").select("name").limit(limit).execute()
    names = [r["name"] for r in (res.data or []) if r.get("name")]
    out = prefixes_from_names(names)
    log.info("harvest: %d prefixes from %d app titles", len(out), len(names))
    return out


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
            if is_noisy(kw):  # drop web-query phrasings before they cost an iTunes call
                continue
            if kw and kw not in avoid:
                seen.setdefault(kw, None)
    log.info("discovery: %d google candidates from %d seeds", len(seen), len(seeds))
    return list(seen)


def clean_noisy(db) -> int:
    """Mark existing pool candidates that are web-query noise as rejected. Self-healing."""
    res = (
        db.table("niche_candidates")
        .select("keyword,status")
        .in_("status", ["new", "validated"])
        .execute()
    )
    n = 0
    for r in res.data or []:
        if is_noisy(r["keyword"]):
            writers.update_candidate(db, r["keyword"], status="rejected", reason="noisy keyword")
            n += 1
    if n:
        log.info("discovery: rejected %d noisy candidates from the pool", n)
    return n


def run_discovery(
    db, itunes: ITunesClient, candidates: list[str], *, weights: dict | None = None
) -> dict:
    """Add new candidates to the pool, then validate+score the backlog (budget-capped).

    Does NOT touch the watch list — discovery only fills a scored candidate pool. The
    operator hand-picks which candidates to track (see `radar --watch`). Each run scores
    `daily_candidate_budget` of the oldest un-validated candidates, so the backlog drains
    over time and the pool keeps deepening.
    """
    w = weights or load_weights()
    cfg = w["discovery"]
    budget = cfg["daily_candidate_budget"]

    # 1. add this run's generated candidates to the pool (status 'new')
    writers.insert_candidates(db, candidates, source="suggest")

    # 2. validate + score the oldest un-validated candidates (this run's + any backlog)
    pending = writers.pending_candidates(db, limit=budget)
    now = datetime.now(timezone.utc).isoformat()
    validated = 0
    rejected = 0

    for kw in pending:
        stubs = search.search(itunes, kw, limit=50)
        ids = [s.app_id for s in stubs]
        metas = lookup.lookup(itunes, ids) if ids else []
        score = score_niche(NicheInputs(apps=metas), w)

        if score.gated_out or len(metas) < cfg["min_apps"]:
            rejected += 1
            reason = score.gate_reason or f"only {len(metas)} apps"
            status = "rejected"
        else:
            validated += 1
            reason = f"opp={score.opportunity:.1f}"
            status = "validated"

        writers.update_candidate(
            db,
            kw,
            status=status,
            best_opportunity=score.opportunity,
            n_apps=len(metas),
            last_checked=now,
            reason=reason,
            app_ids=ids[:30],  # competitive set, for app-set dedup (M9.5)
        )

    summary = {
        "generated": len(candidates),
        "validated": validated,
        "rejected": rejected,
        "scored": len(pending),
    }
    log.info("discovery: scored %d (validated %d, rejected %d)", len(pending), validated, rejected)
    return summary
