"""Ad-hoc calibration report: re-score all niches and print Opportunity + Momentum.

Run: PYTHONPATH=. python scripts/report.py
"""

from __future__ import annotations

from radar.adapters.client import ITunesClient
from radar.adapters.limiter import TokenBucket
from radar.config import Config
from radar.db.client import service_client
from radar.pipeline.score import score_all_niches


def main() -> None:
    cfg = Config.load()
    db = service_client(cfg)
    itunes = ITunesClient(limiter=TokenBucket(per_minute=cfg.rate_limit_per_min))
    try:
        rows = score_all_niches(db, itunes)
    finally:
        itunes.close()

    rows.sort(key=lambda r: (r["momentum"] if r["momentum"] is not None else -1), reverse=True)
    print(f"{'keyword':<26}{'opp':>6}{'mom':>7}{'dem':>6}{'gap':>6}  gate")
    for r in rows:
        mom = "-" if r["momentum"] is None else f"{r['momentum']:.1f}"
        gate = r["gate_reason"] or ""
        print(
            f"{r['keyword']:<26}{r['opportunity']:>6}{mom:>7}"
            f"{r['demand']:>6}{r['gap']:>6}  {gate}"
        )


if __name__ == "__main__":
    main()
