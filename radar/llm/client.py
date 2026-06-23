"""Anthropic client factory (M6.1).

Key is server-side only (Config.require_anthropic → Actions secret / .env), never the
SPA. Lazy import so the package loads without the anthropic dependency present.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from radar.config import Config

if TYPE_CHECKING:
    from anthropic import Anthropic

# Cheap classification model for buildability tagging (PRD §6).
HAIKU = "claude-haiku-4-5-20251001"
# Judgment model for review clustering (PRD §6) — used in M6.3.
SONNET = "claude-sonnet-4-6"


def anthropic_client(config: Config | None = None) -> Anthropic:
    cfg = config or Config.load()
    key = cfg.require_anthropic()  # friendly error before touching the optional dependency
    from anthropic import Anthropic

    return Anthropic(api_key=key)
