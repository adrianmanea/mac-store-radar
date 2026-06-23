"""Lookup adapter (M1.4) — the single biggest rate-limit lever.

`itunes.apple.com/lookup?id=ID1,ID2,...` accepts a comma-separated list. We chunk at
150 ids/call (safe before URL length bites; 150-vs-200 ceiling confirmed empirically —
TASKS open q). 3,000 unique apps -> ~20 calls, not 3,000.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from urllib.parse import urlencode

from radar.adapters._parse import parse_dt
from radar.adapters.client import ITunesClient
from radar.adapters.errors import SchemaError
from radar.adapters.models import AppMetadata

BASE = "https://itunes.apple.com/lookup"
MAX_BATCH = 150


def chunk(ids: Iterable[int], size: int = MAX_BATCH) -> Iterator[list[int]]:
    batch: list[int] = []
    for i in ids:
        batch.append(i)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def build_url(ids: list[int], *, country: str = "us") -> str:
    qs = urlencode({"id": ",".join(str(i) for i in ids), "country": country})
    return f"{BASE}?{qs}"


def _row_to_meta(r: dict) -> AppMetadata | None:
    track_id = r.get("trackId")
    if track_id is None:
        return None
    return AppMetadata(
        app_id=int(track_id),
        name=r.get("trackName", ""),
        bundle_id=r.get("bundleId"),
        developer_id=r.get("artistId"),
        developer_name=r.get("artistName") or r.get("sellerName"),
        category=r.get("primaryGenreName"),
        price=r.get("price"),
        currency=r.get("currency"),
        release_date=parse_dt(r.get("releaseDate")),
        current_ver_date=parse_dt(r.get("currentVersionReleaseDate")),
        version=r.get("version"),
        description=r.get("description"),
        rating_count=r.get("userRatingCount"),
        avg_rating=r.get("averageUserRating"),
    )


def parse(payload: dict) -> list[AppMetadata]:
    if "results" not in payload:
        raise SchemaError("lookup response missing 'results'")
    out: list[AppMetadata] = []
    for r in payload["results"]:
        meta = _row_to_meta(r)
        if meta is not None:
            out.append(meta)
    return out


def lookup(client: ITunesClient, ids: Iterable[int], *, country: str = "us") -> list[AppMetadata]:
    """Batched lookup over an arbitrary number of ids. Dedupes input, preserves order."""
    seen: dict[int, None] = {}
    for i in ids:
        seen.setdefault(int(i), None)
    out: list[AppMetadata] = []
    for batch in chunk(seen.keys()):
        out.extend(parse(client.get_json(build_url(batch, country=country))))
    return out
