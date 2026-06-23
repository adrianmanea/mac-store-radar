"""Normalized adapter outputs (M1).

Adapters return these instead of raw iTunes dicts so the rest of the pipeline (DB
writers, scorer) depends on a stable shape, not Apple's JSON keys. Field names mirror
the DB schema (TECH-PRD §2) to keep the upsert path trivial.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class AppStub:
    """Lightweight result from a search call — enough to dedupe + rank."""

    app_id: int
    name: str
    search_rank: int


@dataclass
class AppMetadata:
    """Full per-app record from a lookup call. Maps onto `apps` + `app_snapshots`."""

    app_id: int
    name: str
    bundle_id: str | None = None
    developer_id: int | None = None
    developer_name: str | None = None
    category: str | None = None
    price: float | None = None
    currency: str | None = None
    has_iap: bool | None = None  # iTunes lookup rarely exposes IAP; best-effort
    is_subscription: bool | None = None
    release_date: datetime | None = None
    current_ver_date: datetime | None = None
    version: str | None = None
    description: str | None = None
    rating_count: int | None = None
    avg_rating: float | None = None
    # Set later by LLM tagging (M6); the lookup adapter leaves it None. The scorer
    # reads it for the buildability multiplier and tolerates None (neutral default).
    complexity_class: str | None = None


@dataclass(frozen=True)
class Review:
    """One customer review for gap mining. Maps onto `reviews`."""

    app_id: int
    apple_review_id: str
    rating: int | None
    title: str | None
    body: str | None
    author: str | None
    submitted_at: datetime | None = None


@dataclass(frozen=True)
class ChartEntry:
    """One ranked app from a chart feed. Only top-free is reliable for Mac."""

    app_id: int
    name: str
    rank: int
    chart: str  # 'top-free' | 'top-paid' | 'top-grossing'


@dataclass(frozen=True)
class Autocomplete:
    """Search-hint depth — a demand proxy. Empty list is a valid degraded result."""

    term: str
    hints: list[str] = field(default_factory=list)

    @property
    def depth(self) -> int:
        return len(self.hints)
