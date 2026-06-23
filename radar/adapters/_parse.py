"""Shared parse helpers for adapters."""

from __future__ import annotations

from datetime import datetime


def parse_dt(value: str | None) -> datetime | None:
    """Parse an iTunes ISO-8601 timestamp ('...Z' or offset) to aware datetime.

    Returns None on missing/unparseable input — a bad date never aborts a parse.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
