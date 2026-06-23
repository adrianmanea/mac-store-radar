"""Compare search results WITH vs WITHOUT the trailing 'mac' suffix (read-only).

There's no automatic "better" — no install/click ground truth. This makes the
difference legible so you can judge which competitive set is the real one:
  - result count each way
  - Jaccard overlap of the app-id sets (how much they agree)
  - top apps each way (so you see what the suffix adds/drops)
  - the resulting sub-scores + Opportunity each way (does the score move?)

No DB writes. Hits iTunes live (throttled). Usage:
  PYTHONPATH=. python scripts/compare_suffix.py "clipboard manager" "pdf editor"
"""

from __future__ import annotations

import sys

from radar.adapters import lookup, search
from radar.adapters.client import ITunesClient
from radar.adapters.limiter import TokenBucket
from radar.scoring.engine import NicheInputs, score_niche

DEFAULT = ["clipboard manager", "pdf editor", "android file transfer"]


def _score(itunes, term: str):
    stubs = search.search(itunes, term, limit=50)
    ids = [s.app_id for s in stubs]
    metas = lookup.lookup(itunes, ids)
    s = score_niche(NicheInputs(apps=metas))
    top = [m.name for m in sorted(metas, key=lambda m: m.rating_count or 0, reverse=True)[:5]]
    return {"ids": set(ids), "n": len(ids), "score": s, "top": top}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a | b) else 0.0


def main() -> None:
    bases = sys.argv[1:] or DEFAULT
    itunes = ITunesClient(limiter=TokenBucket(per_minute=18))
    try:
        for base in bases:
            base = base.removesuffix(" mac").strip()
            without = _score(itunes, base)
            withm = _score(itunes, f"{base} mac")

            print(f"\n=== {base!r} ===")
            print(f"  results:     without={without['n']:<4} with_mac={withm['n']}")
            ov = jaccard(without["ids"], withm["ids"])
            print(f"  set overlap: {ov:.0%} (Jaccard of app ids)")
            for label, r in (("without", without), ("with mac", withm)):
                sc = r["score"]
                gate = f" GATED({sc.gate_reason})" if sc.gated_out else ""
                print(
                    f"  [{label:<8}] opp={sc.opportunity:5.1f} "
                    f"dem={sc.demand:4.1f} comp={sc.competition:4.1f} "
                    f"gap={sc.gap:4.1f} mon={sc.monetization:4.1f}{gate}"
                )
            print(f"  top without: {', '.join(without['top'])}")
            print(f"  top with:    {', '.join(withm['top'])}")
    finally:
        itunes.close()


if __name__ == "__main__":
    main()
