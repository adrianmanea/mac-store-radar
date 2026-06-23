"""Shared parse helpers for adapters."""

from __future__ import annotations

import re
from datetime import datetime

# Normalize variable-length fractional seconds (Postgres can return 5 digits) to the
# 6 that datetime.fromisoformat requires on Python < 3.11.
_FRACTION = re.compile(r"\.(\d+)")


def parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp ('...Z', offset, any fractional precision) to aware dt.

    Returns None on missing/unparseable input — a bad date never aborts a parse.
    """
    if not value:
        return None
    try:
        normalized = _FRACTION.sub(lambda m: "." + (m.group(1) + "000000")[:6], value)
        return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
