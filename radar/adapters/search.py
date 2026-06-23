"""Search adapter (M1.3).

`itunes.apple.com/search?term=&entity=macSoftware&country=us&limit=200`
One call per keyword. Returns ranked AppStubs for dedupe + niche_apps rows.
"""

from __future__ import annotations

from urllib.parse import urlencode

from radar.adapters.client import ITunesClient
from radar.adapters.errors import SchemaError
from radar.adapters.models import AppStub

BASE = "https://itunes.apple.com/search"


def build_url(term: str, *, country: str = "us", limit: int = 200) -> str:
    qs = urlencode({"term": term, "entity": "macSoftware", "country": country, "limit": limit})
    return f"{BASE}?{qs}"


def parse(payload: dict) -> list[AppStub]:
    if "results" not in payload:
        raise SchemaError("search response missing 'results'")
    stubs: list[AppStub] = []
    for rank, r in enumerate(payload["results"], start=1):
        track_id = r.get("trackId")
        if track_id is None:
            continue  # tolerate odd rows, don't abort the niche
        stubs.append(AppStub(app_id=int(track_id), name=r.get("trackName", ""), search_rank=rank))
    return stubs


def search(
    client: ITunesClient, term: str, *, country: str = "us", limit: int = 200
) -> list[AppStub]:
    return parse(client.get_json(build_url(term, country=country, limit=limit)))
