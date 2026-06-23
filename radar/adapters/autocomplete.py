"""Autocomplete adapter (M1.7) — unofficial, fully isolated.

Endpoint: search.itunes.apple.com/WebObjects/MZSearchHints.woa/wa/hints
Returns a **plist (XML)** payload, not JSON, with a top-level 'hints' list. Used purely
as a demand-proxy depth signal (how many suggestions Apple offers for a term).

VERIFIED AT BUILD: this endpoint is brittle — it returned 0 hints in probing and may
break without notice. Per TECH-PRD §3 it is isolated here so a break is a one-file fix;
an empty/garbled response degrades to depth 0 rather than failing the run.
"""

from __future__ import annotations

import plistlib

from radar.adapters.client import ITunesClient
from radar.adapters.models import Autocomplete

BASE = "https://search.itunes.apple.com/WebObjects/MZSearchHints.woa/wa/hints"


def build_url(term: str) -> str:
    from urllib.parse import urlencode

    return f"{BASE}?{urlencode({'clientApplication': 'Software', 'term': term})}"


def parse(term: str, body: bytes) -> Autocomplete:
    """Parse the plist body. Any malformed/empty payload -> depth 0 (graceful degrade)."""
    try:
        data = plistlib.loads(body)
    except Exception:  # noqa: BLE001 - unofficial endpoint, tolerate any garbage
        return Autocomplete(term=term, hints=[])
    hints = data.get("hints", []) if isinstance(data, dict) else []
    terms = [h.get("term") for h in hints if isinstance(h, dict) and h.get("term")]
    return Autocomplete(term=term, hints=terms)


def autocomplete(client: ITunesClient, term: str) -> Autocomplete:
    return parse(term, client.get_bytes(build_url(term)))
