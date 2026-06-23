"""Supabase client factory (M2.3).

Creates a service-role client for the pipeline (writes bypass RLS). The supabase import
is local so the rest of the package — adapters, scoring, row builders — imports without
the dependency present (keeps tests light).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from radar.config import Config

if TYPE_CHECKING:
    from supabase import Client


def service_client(config: Config | None = None) -> Client:
    """Service-role Supabase client. Use only in the pipeline (Actions), never the SPA."""
    from supabase import create_client

    cfg = config or Config.load()
    return create_client(cfg.supabase_url, cfg.supabase_service_key)
