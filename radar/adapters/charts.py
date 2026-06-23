"""Charts adapter (M1.6).

VERIFIED AT BUILD: for Mac, only **top-free** returns data. `topgrossingmacapps` and
`toppaidmacapps` returned empty feeds. So charts give at best a top-free rank-presence
signal; **proven monetization comes from the metadata paid/sub ratio fallback**
(monetization_score in M3, TECH-PRD §9). This resolves the §12 open question: do NOT
depend on a Mac grossing feed.
"""

from __future__ import annotations

from radar.adapters.client import ITunesClient
from radar.adapters.errors import SchemaError
from radar.adapters.models import ChartEntry

# Only top-free is reliable for Mac. Kept as a map so a feed coming back to life later
# is a one-line addition, not a code change.
FEEDS = {
    "top-free": "topfreemacapps",
    "top-paid": "toppaidmacapps",  # currently empty for Mac
    "top-grossing": "topgrossingmacapps",  # currently empty for Mac
}


def build_url(chart: str, *, country: str = "us", limit: int = 100) -> str:
    if chart not in FEEDS:
        raise ValueError(f"unknown chart {chart!r}; expected one of {list(FEEDS)}")
    return f"https://itunes.apple.com/{country}/rss/{FEEDS[chart]}/limit={limit}/json"


def parse(chart: str, payload: dict) -> list[ChartEntry]:
    feed = payload.get("feed")
    if feed is None:
        raise SchemaError("charts response missing 'feed'")
    entries = feed.get("entry", [])
    out: list[ChartEntry] = []
    for rank, e in enumerate(entries, start=1):
        im_id = ((e.get("id") or {}).get("attributes") or {}).get("im:id")
        if im_id is None:
            continue
        out.append(
            ChartEntry(
                app_id=int(im_id),
                name=(e.get("im:name") or {}).get("label", ""),
                rank=rank,
                chart=chart,
            )
        )
    return out


def charts(
    client: ITunesClient, chart: str = "top-free", *, country: str = "us", limit: int = 100
) -> list[ChartEntry]:
    """Fetch a chart feed. Empty result is valid (and expected for Mac paid/grossing)."""
    return parse(chart, client.get_json(build_url(chart, country=country, limit=limit)))
