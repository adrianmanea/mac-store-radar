"""Pure row builders (M2.4–2.7).

Turn normalized adapter models into the dict rows Supabase expects. Kept free of any
supabase import so they're unit-testable offline. Datetimes serialize to ISO strings.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from radar.adapters.models import AppMetadata, ChartEntry, Review


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def app_row(meta: AppMetadata, *, captured_at: datetime) -> dict[str, Any]:
    """Row for `apps` upsert. last_seen bumped to the run timestamp."""
    return {
        "app_id": meta.app_id,
        "bundle_id": meta.bundle_id,
        "name": meta.name,
        "developer_id": meta.developer_id,
        "developer_name": meta.developer_name,
        "category": meta.category,
        "price": meta.price,
        "currency": meta.currency,
        "has_iap": meta.has_iap,
        "is_subscription": meta.is_subscription,
        "release_date": _iso(meta.release_date),
        "current_ver_date": _iso(meta.current_ver_date),
        "description": meta.description,
        "last_seen": _iso(captured_at),
    }


def snapshot_row(
    meta: AppMetadata, *, captured_at: datetime, chart_rank: int | None = None
) -> dict[str, Any]:
    """Row for `app_snapshots` — the time-series spine of momentum."""
    return {
        "app_id": meta.app_id,
        "captured_at": _iso(captured_at),
        "rating_count": meta.rating_count,
        "avg_rating": meta.avg_rating,
        "price": meta.price,
        "version": meta.version,
        "chart_rank": chart_rank,
    }


def niche_app_row(
    niche_id: int, app_id: int, search_rank: int, *, captured_at: datetime
) -> dict[str, Any]:
    return {
        "niche_id": niche_id,
        "app_id": app_id,
        "search_rank": search_rank,
        "captured_at": _iso(captured_at),
    }


def review_row(review: Review) -> dict[str, Any]:
    return {
        "app_id": review.app_id,
        "apple_review_id": review.apple_review_id,
        "rating": review.rating,
        "title": review.title,
        "body": review.body,
        "author": review.author,
        "submitted_at": _iso(review.submitted_at),
    }


def chart_rank_map(entries: list[ChartEntry]) -> dict[int, int]:
    """app_id -> rank, for stamping chart_rank onto snapshots."""
    return {e.app_id: e.rank for e in entries}
