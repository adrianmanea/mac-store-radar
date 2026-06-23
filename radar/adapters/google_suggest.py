"""Google Suggest adapter (M9.6) — free, live, high-volume keyword source.

Apple's own autocomplete is dead (0 hints), but Google's public suggest endpoint
returns real search completions. Used as a discovery generator (expand seed prefixes
into the queries people actually type) and as a demand proxy (a query Google bothers to
suggest has real volume).

Endpoint: suggestqueries.google.com/complete/search?client=firefox&q=<prefix>
Response: ["<query>", ["suggestion1","suggestion2",...], [], {...}]  (a JSON array)
Unofficial — isolated here so a break is a one-file fix.
"""

from __future__ import annotations

import json
from urllib.parse import urlencode

from radar.adapters.client import ITunesClient

BASE = "https://suggestqueries.google.com/complete/search"


def build_url(prefix: str) -> str:
    return f"{BASE}?{urlencode({'client': 'firefox', 'q': prefix})}"


def parse(body: bytes) -> list[str]:
    """Extract the suggestion list. Any malformed payload -> [] (graceful degrade)."""
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return []
    if not (isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list)):
        return []
    return [s.strip() for s in data[1] if isinstance(s, str) and s.strip()]


def suggest(client: ITunesClient, prefix: str) -> list[str]:
    """Return Google's autocomplete suggestions for `prefix` (most-popular first)."""
    return parse(client.get_bytes(build_url(prefix)))
