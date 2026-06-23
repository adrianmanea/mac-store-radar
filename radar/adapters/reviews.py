"""Reviews adapter (M1.5).

`itunes.apple.com/{cc}/rss/customerreviews/id={id}/sortBy=mostRecent/page={n}/json`
Paginated (~10 pages), recent-only, ~500 cap.

KNOWN RISK (verified at build): the customerreviews RSS feed returned **empty for every
Mac app probed**. The adapter is correct against the documented shape; an empty feed is
returned as `[]`, not an error. The gap signal degrades gracefully when reviews are
absent (scoring stubs complaint density). Revisit if/when Mac review data appears.
"""

from __future__ import annotations

from radar.adapters._parse import parse_dt
from radar.adapters.client import ITunesClient
from radar.adapters.errors import SchemaError
from radar.adapters.models import Review

MAX_PAGES = 10


def build_url(app_id: int, page: int, *, country: str = "us") -> str:
    return (
        f"https://itunes.apple.com/{country}/rss/customerreviews/"
        f"id={app_id}/sortBy=mostRecent/page={page}/json"
    )


def parse_page(app_id: int, payload: dict) -> list[Review]:
    feed = payload.get("feed")
    if feed is None:
        raise SchemaError("reviews response missing 'feed'")
    entries = feed.get("entry", [])
    # The first entry is app metadata, not a review, when reviews are present.
    # When the feed is empty Apple omits 'entry' entirely -> [] (the common Mac case).
    out: list[Review] = []
    for e in entries:
        rid = (e.get("id") or {}).get("label")
        if rid is None:
            continue  # skips the leading metadata entry, which has no review id shape
        rating = (e.get("im:rating") or {}).get("label")
        out.append(
            Review(
                app_id=app_id,
                apple_review_id=str(rid),
                rating=int(rating) if rating and rating.isdigit() else None,
                title=(e.get("title") or {}).get("label"),
                body=(e.get("content") or {}).get("label"),
                author=((e.get("author") or {}).get("name") or {}).get("label"),
                submitted_at=parse_dt((e.get("updated") or {}).get("label")),
            )
        )
    return out


def reviews(
    client: ITunesClient, app_id: int, *, country: str = "us", max_pages: int = MAX_PAGES
) -> list[Review]:
    """Fetch recent reviews across pages. Stops early on an empty page. Dedupes by id."""
    collected: dict[str, Review] = {}
    for page in range(1, max_pages + 1):
        page_reviews = parse_page(app_id, client.get_json(build_url(app_id, page, country=country)))
        if not page_reviews:
            break
        for r in page_reviews:
            collected[r.apple_review_id] = r
    return list(collected.values())
